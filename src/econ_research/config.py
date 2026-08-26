from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_default_model: str = Field(
        default="gpt-5.6-terra",
        validation_alias=AliasChoices("OPENAI_DEFAULT_MODEL", "OPENAI_MODEL"),
    )
    openai_card_model: str | None = Field(default="gpt-5.6-luna", alias="OPENAI_CARD_MODEL")
    openai_deep_read_model: str | None = Field(
        default="gpt-5.6-terra", alias="OPENAI_DEEP_READ_MODEL"
    )
    openai_card_reasoning_effort: ReasoningEffort = Field(
        default="low", alias="OPENAI_CARD_REASONING_EFFORT"
    )
    openai_deep_read_reasoning_effort: ReasoningEffort = Field(
        default="medium", alias="OPENAI_DEEP_READ_REASONING_EFFORT"
    )
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

    @property
    def effective_card_model(self) -> str:
        return self.openai_card_model or self.openai_default_model

    @property
    def effective_deep_read_model(self) -> str:
        return self.openai_deep_read_model or self.openai_default_model

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.originals_dir, self.parsed_dir, self.generated_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
