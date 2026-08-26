from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    data_dir: Path = Field(default=Path("data"), alias="ECON_RESEARCH_DATA_DIR")
    db_path: Path = Field(default=Path("data/research.db"), alias="ECON_RESEARCH_DB_PATH")

    @property
    def originals_dir(self) -> Path:
        return self.data_dir / "originals"

    @property
    def parsed_dir(self) -> Path:
        return self.data_dir / "parsed"

    @property
    def generated_dir(self) -> Path:
        return self.data_dir / "generated"

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.originals_dir, self.parsed_dir, self.generated_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings

