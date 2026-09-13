"""Loading of recorded canonical datasets for deterministic runs and tests."""

from __future__ import annotations

import json
from pathlib import Path

from stocks_infer.models import ScreeningRecord


def load_screening_records(path: Path) -> tuple[ScreeningRecord, ...]:
    with path.open("r", encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if not isinstance(payload, list):
        raise ValueError("recorded screening dataset must be a JSON array")

    records = tuple(ScreeningRecord.from_dict(item) for item in payload)
    if not records:
        raise ValueError("recorded screening dataset cannot be empty")
    return records
