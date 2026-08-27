from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from econ_research.models import (
    CardType,
    ClaimKind,
    DeepReadResult,
    DeepReadSummary,
    LLMCall,
    LLMCallMetrics,
    Paper,
    ParsedDocument,
    ResearchCard,
    ResearchCardDraft,
    SearchResult,
    SourceChunk,
    UsageReport,
    UsageSummary,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = files("econ_research.db").joinpath("schema.sql").read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(schema)

    def find_by_sha256(self, sha256: str) -> Paper | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM papers WHERE sha256 = ?", (sha256,)).fetchone()
        return self._paper_from_row(row) if row else None

    def create_processing_paper(
        self, paper_id: str, sha256: str, source_filename: str, pdf_path: str
    ) -> Paper:
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO papers
                   (id, sha256, source_filename, pdf_path, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'processing', ?, ?)""",
                (paper_id, sha256, source_filename, pdf_path, timestamp, timestamp),
            )
        paper = self.get_paper(paper_id)
        assert paper is not None
        return paper

    def restart_failed_paper(self, paper_id: str, source_filename: str, pdf_path: str) -> None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT status FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
            if not row or row["status"] != "failed":
                raise ValueError(f"Only a failed paper can be restarted: {paper_id}")
            connection.execute("DELETE FROM search_index WHERE paper_id = ?", (paper_id,))
            connection.execute("DELETE FROM deep_reads WHERE paper_id = ?", (paper_id,))
            connection.execute("DELETE FROM cards WHERE paper_id = ?", (paper_id,))
            connection.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
            connection.execute(
                """UPDATE papers SET source_filename = ?, pdf_path = ?, markdown_path = NULL,
                   status = 'processing', error = NULL, updated_at = ? WHERE id = ?""",
                (source_filename, pdf_path, utc_now(), paper_id),
            )

    def finalize_ingest(
        self,
        paper_id: str,
        markdown_path: str,
        document: ParsedDocument,
        cards: list[ResearchCardDraft],
    ) -> tuple[int, int]:
        timestamp = utc_now()
        chunk_ids: dict[int, str] = {}
        with self.connect() as connection:
            connection.execute("DELETE FROM search_index WHERE paper_id = ?", (paper_id,))
            for chunk in document.chunks:
                chunk_id = str(uuid4())
                chunk_ids[chunk.ordinal] = chunk_id
                connection.execute(
                    """INSERT INTO chunks
                       (id, paper_id, ordinal, text, section, page_start, page_end)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id,
                        paper_id,
                        chunk.ordinal,
                        chunk.text,
                        chunk.section,
                        chunk.page_start,
                        chunk.page_end,
                    ),
                )
                connection.execute(
                    """INSERT INTO search_index
                       (entity_type, entity_id, paper_id, title, content, section,
                        page_start, page_end) VALUES ('chunk', ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id,
                        paper_id,
                        chunk.section or f"Source passage {chunk.ordinal + 1}",
                        chunk.text,
                        chunk.section,
                        chunk.page_start,
                        chunk.page_end,
                    ),
                )

            for card in cards:
                card_id = str(uuid4())
                source_chunk = (
                    next(
                        (
                            chunk
                            for chunk in document.chunks
                            if chunk.ordinal == card.chunk_ordinal
                        ),
                        None,
                    )
                    if card.chunk_ordinal is not None
                    else None
                )
                chunk_id = (
                    chunk_ids.get(card.chunk_ordinal)
                    if card.chunk_ordinal is not None
                    else None
                )
                section = card.section or (source_chunk.section if source_chunk else None)
                page_start = card.page_start or (source_chunk.page_start if source_chunk else None)
                page_end = card.page_end or (source_chunk.page_end if source_chunk else None)
                connection.execute(
                    """INSERT INTO cards
                       (id, paper_id, chunk_id, type, title, content, section, page_start,
                        page_end, tags_json, claim_kind, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        card_id,
                        paper_id,
                        chunk_id,
                        card.type,
                        card.title,
                        card.content,
                        section,
                        page_start,
                        page_end,
                        json.dumps(card.tags, ensure_ascii=False),
                        card.claim_kind,
                        timestamp,
                    ),
                )
                connection.execute(
                    """INSERT INTO search_index
                       (entity_type, entity_id, paper_id, title, content, section,
                        page_start, page_end) VALUES ('card', ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        card_id,
                        paper_id,
                        card.title,
                        f"{card.type} {card.claim_kind} {card.content} {' '.join(card.tags)}",
                        section,
                        page_start,
                        page_end,
                    ),
                )

            connection.execute(
                """UPDATE papers SET markdown_path = ?, title = ?, authors_json = ?, year = ?,
                   status = 'ready', error = NULL, updated_at = ? WHERE id = ?""",
                (
                    markdown_path,
                    document.title,
                    json.dumps(document.authors, ensure_ascii=False),
                    document.year,
                    timestamp,
                    paper_id,
                ),
            )
            connection.execute(
                """INSERT INTO search_index
                   (entity_type, entity_id, paper_id, title, content, section,
                    page_start, page_end) VALUES ('paper', ?, ?, ?, ?, NULL, NULL, NULL)""",
                (
                    paper_id,
                    paper_id,
                    document.title,
                    " ".join([document.title, *document.authors, str(document.year or "")]),
                ),
            )
        return len(document.chunks), len(cards)

    def mark_failed(self, paper_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE papers SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                (error[:2000], utc_now(), paper_id),
            )

    def refresh_parsed_document(
        self, paper_id: str, markdown_path: str, document: ParsedDocument
    ) -> int:
        """Replace derived chunks without calling an LLM and reconnect cards by stable ordinal."""
        timestamp = utc_now()
        chunk_ids: dict[int, str] = {}
        chunk_by_ordinal = {chunk.ordinal: chunk for chunk in document.chunks}
        with self.connect() as connection:
            card_sources = {
                row["id"]: row["ordinal"]
                for row in connection.execute(
                    """SELECT cards.id, chunks.ordinal FROM cards
                       LEFT JOIN chunks ON chunks.id = cards.chunk_id
                       WHERE cards.paper_id = ?""",
                    (paper_id,),
                ).fetchall()
            }
            connection.execute("DELETE FROM search_index WHERE paper_id = ?", (paper_id,))
            connection.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
            for chunk in document.chunks:
                chunk_id = str(uuid4())
                chunk_ids[chunk.ordinal] = chunk_id
                connection.execute(
                    """INSERT INTO chunks
                       (id, paper_id, ordinal, text, section, page_start, page_end)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id,
                        paper_id,
                        chunk.ordinal,
                        chunk.text,
                        chunk.section,
                        chunk.page_start,
                        chunk.page_end,
                    ),
                )
                connection.execute(
                    """INSERT INTO search_index
                       (entity_type, entity_id, paper_id, title, content, section,
                        page_start, page_end) VALUES ('chunk', ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id,
                        paper_id,
                        chunk.section or f"Source passage {chunk.ordinal + 1}",
                        chunk.text,
                        chunk.section,
                        chunk.page_start,
                        chunk.page_end,
                    ),
                )
            reconnected = 0
            for card_id, ordinal in card_sources.items():
                chunk = chunk_by_ordinal.get(ordinal) if ordinal is not None else None
                if chunk is not None:
                    reconnected += 1
                connection.execute(
                    """UPDATE cards SET chunk_id = ?, section = COALESCE(section, ?),
                       page_start = COALESCE(page_start, ?), page_end = COALESCE(page_end, ?)
                       WHERE id = ?""",
                    (
                        chunk_ids.get(ordinal),
                        chunk.section if chunk else None,
                        chunk.page_start if chunk else None,
                        chunk.page_end if chunk else None,
                        card_id,
                    ),
                )
            cards = connection.execute(
                "SELECT * FROM cards WHERE paper_id = ?", (paper_id,)
            ).fetchall()
            for card in cards:
                connection.execute(
                    """INSERT INTO search_index
                       (entity_type, entity_id, paper_id, title, content, section,
                        page_start, page_end) VALUES ('card', ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        card["id"],
                        paper_id,
                        card["title"],
                        (
                            f"{card['type']} {card['claim_kind']} {card['content']} "
                            f"{card['tags_json']}"
                        ),
                        card["section"],
                        card["page_start"],
                        card["page_end"],
                    ),
                )
            connection.execute(
                """UPDATE papers SET markdown_path = ?, title = ?, authors_json = ?, year = ?,
                   updated_at = ? WHERE id = ?""",
                (
                    markdown_path,
                    document.title,
                    json.dumps(document.authors, ensure_ascii=False),
                    document.year,
                    timestamp,
                    paper_id,
                ),
            )
            connection.execute(
                """INSERT INTO search_index
                   (entity_type, entity_id, paper_id, title, content, section,
                    page_start, page_end) VALUES ('paper', ?, ?, ?, ?, NULL, NULL, NULL)""",
                (
                    paper_id,
                    paper_id,
                    document.title,
                    " ".join([document.title, *document.authors, str(document.year or "")]),
                ),
            )
        return reconnected

    def get_paper(self, paper_id: str) -> Paper | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return self._paper_from_row(row) if row else None

    def list_papers(self) -> list[Paper]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM papers ORDER BY created_at DESC").fetchall()
        return [self._paper_from_row(row) for row in rows]

    def get_chunks(self, paper_id: str) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE paper_id = ? ORDER BY ordinal", (paper_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def count_cards(self, paper_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM cards WHERE paper_id = ?", (paper_id,)
            ).fetchone()
        return int(row["count"])

    def list_cards(
        self,
        *,
        paper_id: str | None = None,
        card_type: CardType | None = None,
        claim_kind: ClaimKind | None = None,
        limit: int = 200,
    ) -> list[ResearchCard]:
        clauses: list[str] = []
        parameters: list[object] = []
        if paper_id:
            clauses.append("cards.paper_id = ?")
            parameters.append(paper_id)
        if card_type:
            clauses.append("cards.type = ?")
            parameters.append(card_type)
        if claim_kind:
            clauses.append("cards.claim_kind = ?")
            parameters.append(claim_kind)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT cards.*, chunks.ordinal AS chunk_ordinal
                    FROM cards LEFT JOIN chunks ON chunks.id = cards.chunk_id
                    {where} ORDER BY cards.created_at DESC, cards.rowid LIMIT ?""",
                parameters,
            ).fetchall()
        cards: list[ResearchCard] = []
        for row in rows:
            values = dict(row)
            values["tags"] = json.loads(values.pop("tags_json"))
            cards.append(ResearchCard(**values))
        return cards

    def list_source_chunks(self, paper_id: str) -> list[SourceChunk]:
        return [SourceChunk(**chunk) for chunk in self.get_chunks(paper_id)]

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        if not query.strip():
            return []
        literal_query = f'"{query.strip().replace(chr(34), chr(34) * 2)}"'
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT entity_type, entity_id, paper_id, title,
                          snippet(search_index, 4, '[', ']', ' … ', 24) AS snippet,
                          bm25(search_index, 0.0, 0.0, 0.0, 3.0, 1.0) AS rank,
                          section, page_start, page_end
                   FROM search_index WHERE search_index MATCH ?
                   ORDER BY rank LIMIT ?""",
                (literal_query, limit),
            ).fetchall()
        return [SearchResult(**dict(row)) for row in rows]

    def save_deep_read(self, paper_id: str, focus: str | None, report: str) -> DeepReadResult:
        result = DeepReadResult(
            id=str(uuid4()), paper_id=paper_id, focus=focus, report=report, created_at=utc_now()
        )
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO deep_reads (id, paper_id, focus, report, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (result.id, result.paper_id, result.focus, result.report, result.created_at),
            )
        return result

    def list_deep_reads(self, paper_id: str) -> list[DeepReadSummary]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, paper_id, focus,
                          CASE WHEN length(report) > 240
                               THEN substr(report, 1, 240) || '…' ELSE report END AS preview,
                          created_at
                   FROM deep_reads WHERE paper_id = ? ORDER BY created_at DESC""",
                (paper_id,),
            ).fetchall()
        return [DeepReadSummary(**dict(row)) for row in rows]

    def get_deep_read(self, deep_read_id: str) -> DeepReadResult | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM deep_reads WHERE id = ?", (deep_read_id,)
            ).fetchone()
        return DeepReadResult(**dict(row)) if row else None

    def save_llm_call(
        self,
        paper_id: str,
        operation: str,
        metrics: LLMCallMetrics,
    ) -> LLMCall:
        call = LLMCall(
            id=str(uuid4()), paper_id=paper_id, operation=operation, **metrics.model_dump()
        )
        values = call.model_dump()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO llm_calls (
                       id, paper_id, operation, provider_request_id, model, reasoning_effort,
                       input_tokens, cached_input_tokens, cache_write_tokens, output_tokens,
                       reasoning_tokens, total_tokens, input_price_per_million,
                       cached_input_price_per_million, cache_write_price_per_million,
                       output_price_per_million, estimated_cost_usd, duration_ms, status, error,
                       started_at, completed_at
                   ) VALUES (
                       :id, :paper_id, :operation, :provider_request_id, :model,
                       :reasoning_effort, :input_tokens, :cached_input_tokens,
                       :cache_write_tokens, :output_tokens, :reasoning_tokens, :total_tokens,
                       :input_price_per_million, :cached_input_price_per_million,
                       :cache_write_price_per_million, :output_price_per_million,
                       :estimated_cost_usd, :duration_ms, :status, :error, :started_at,
                       :completed_at
                   )""",
                values,
            )
        return call

    def usage_report(
        self,
        *,
        paper_id: str | None = None,
        operation: str | None = None,
        since: str | None = None,
        include_calls: bool = False,
    ) -> UsageReport:
        clauses: list[str] = []
        parameters: list[str] = []
        if paper_id:
            clauses.append("paper_id = ?")
            parameters.append(paper_id)
        if operation:
            clauses.append("operation = ?")
            parameters.append(operation)
        if since:
            clauses.append("started_at >= ?")
            parameters.append(since)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            row = connection.execute(
                f"""SELECT
                       COUNT(*) AS call_count,
                       COALESCE(SUM(status = 'succeeded'), 0) AS succeeded_count,
                       COALESCE(SUM(status = 'failed'), 0) AS failed_count,
                       COALESCE(SUM(estimated_cost_usd IS NULL), 0) AS unpriced_count,
                       COALESCE(SUM(input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
                       COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens,
                       COALESCE(SUM(output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COALESCE(SUM(duration_ms), 0) AS total_duration_ms,
                       COALESCE(AVG(duration_ms), 0) AS average_duration_ms,
                       COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
                   FROM llm_calls{where}""",
                parameters,
            ).fetchone()
            rows = (
                connection.execute(
                    f"SELECT * FROM llm_calls{where} ORDER BY started_at DESC", parameters
                ).fetchall()
                if include_calls
                else []
            )
        summary_values = dict(row)
        summary_values["average_duration_ms"] = round(
            float(summary_values["average_duration_ms"]), 2
        )
        summary_values["estimated_cost_usd"] = round(
            float(summary_values["estimated_cost_usd"]), 8
        )
        return UsageReport(
            summary=UsageSummary(**summary_values),
            calls=[LLMCall(**dict(call_row)) for call_row in rows] if include_calls else None,
        )

    @staticmethod
    def _paper_from_row(row: sqlite3.Row) -> Paper:
        values = dict(row)
        values["authors"] = json.loads(values.pop("authors_json"))
        return Paper(**values)
