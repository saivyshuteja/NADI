from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NADI9_", env_file=".env", extra="ignore")

    mode: str = Field(default="mock", description="mock | live")
    max_model_calls: int = 25
    max_tool_calls: int = 50
    data_dir: Path = ROOT / "data" / "raw"
    output_dir: Path = ROOT / "sample_run"
    db_path: Path = ROOT / "data" / "processed" / "nadi9.sqlite"
    llm_model: str = "gpt-4o-mini"
    release_confidence_threshold: float = 0.82
    retrieve_top_k: int = 8
    max_cps: float = 20.0

    @property
    def is_mock(self) -> bool:
        return self.mode.lower() != "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
