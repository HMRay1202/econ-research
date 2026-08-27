from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from econ_research.models import ParsedDocument


class Parser(Protocol):
    def parse(
        self,
        pdf_path: Path,
        on_progress: Callable[[str, int, str], None] | None = None,
    ) -> ParsedDocument: ...
