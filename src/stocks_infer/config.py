"""Application configuration loaded from explicit values or environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime settings that are independent of any particular data provider."""

    output_root: Path = Path(".")
    shortlist_size: int = 50
    cache_raw_responses: bool = True

    def __post_init__(self) -> None:
        if self.shortlist_size < 1:
            raise ValueError("shortlist_size must be at least 1")

    @classmethod
    def from_environment(cls) -> "AppConfig":
        return cls(
            output_root=Path(os.getenv("STOCKS_INFER_OUTPUT_ROOT", ".")),
            shortlist_size=int(os.getenv("STOCKS_INFER_SHORTLIST_SIZE", "50")),
            cache_raw_responses=_environment_flag(
                "STOCKS_INFER_CACHE_RAW_RESPONSES", default=True
            ),
        )


def _environment_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")
