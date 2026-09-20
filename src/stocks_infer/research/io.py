"""Strict JSON boundary and canonical serialization for research bundles."""

from dataclasses import asdict, is_dataclass
from datetime import date
import hashlib
import json
from pathlib import Path

from stocks_infer.research.models import (
    Claim, Company, FinancialFact, MarketObservation, ResearchBundle,
    Scenario, SourceDocument, Thesis,
)


def json_value(value):
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def canonical_json(value) -> str:
    return json.dumps(json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(json_value(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _parse(cls, raw, dates=(), tuples=()):
    data = dict(raw)
    for key in dates:
        if data.get(key) is not None:
            data[key] = date.fromisoformat(data[key])
    for key in tuples:
        if key in data:
            data[key] = tuple(data[key])
    try:
        return cls(**data)
    except TypeError as error:
        raise ValueError(f"invalid {cls.__name__}: {error}") from error


def load_bundle(path: Path) -> ResearchBundle:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) - {"schema_version", "companies", "sources", "facts", "prices", "theses", "scenarios"}:
        raise ValueError("invalid research bundle object or unknown fields")
    theses = []
    for item in raw.get("theses", []):
        data = dict(item)
        data["claims"] = tuple(_parse(Claim, c, ("review_on",), ("source_ids",)) for c in data.get("claims", []))
        theses.append(_parse(Thesis, data, ("authored_at", "next_review")))
    return ResearchBundle(
        schema_version=raw.get("schema_version", 1),
        companies=tuple(_parse(Company, c, ("classified_at",)) for c in raw.get("companies", [])),
        sources=tuple(_parse(SourceDocument, s, ("published_at", "retrieved_at")) for s in raw.get("sources", [])),
        facts=tuple(_parse(FinancialFact, f, ("period_start", "period_end", "available_at")) for f in raw.get("facts", [])),
        prices=tuple(_parse(MarketObservation, p, ("price_date", "available_at", "share_count_date")) for p in raw.get("prices", [])),
        theses=tuple(theses),
        scenarios=tuple(_parse(Scenario, s, ("authored_at",), ("claim_ids", "revenue_growth", "operating_margins")) for s in raw.get("scenarios", [])),
    )
