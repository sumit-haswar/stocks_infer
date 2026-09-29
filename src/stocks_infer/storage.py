"""Local raw cache, Parquet snapshots, and reproducible run artifacts."""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import date, datetime
import gzip
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from stocks_infer.models import RunManifest, ScreeningRecord, StockScore


SCREENING_RECORD_SCHEMA: tuple[tuple[str, str], ...] = (
    ("security_id", "VARCHAR"),
    ("ticker", "VARCHAR"),
    ("name", "VARCHAR"),
    ("exchange", "VARCHAR"),
    ("as_of_date", "DATE"),
    ("period_end", "DATE"),
    ("available_at", "DATE"),
    ("price_date", "DATE"),
    ("fundamentals_source", "VARCHAR"),
    ("price_source", "VARCHAR"),
    ("adjusted_close", "DOUBLE"),
    ("security_type", "VARCHAR"),
    ("currency", "VARCHAR"),
    ("cik", "VARCHAR"),
    ("figi", "VARCHAR"),
    ("sector", "VARCHAR"),
    ("industry", "VARCHAR"),
    ("average_daily_volume", "DOUBLE"),
    ("market_cap", "DOUBLE"),
    ("enterprise_value", "DOUBLE"),
    ("revenue_ttm", "DOUBLE"),
    ("revenue_prior_ttm", "DOUBLE"),
    ("gross_profit_ttm", "DOUBLE"),
    ("gross_profit_prior_ttm", "DOUBLE"),
    ("ebit_ttm", "DOUBLE"),
    ("net_income_ttm", "DOUBLE"),
    ("net_income_prior_ttm", "DOUBLE"),
    ("operating_cash_flow_ttm", "DOUBLE"),
    ("operating_cash_flow_prior_ttm", "DOUBLE"),
    ("free_cash_flow_ttm", "DOUBLE"),
    ("free_cash_flow_prior_ttm", "DOUBLE"),
    ("total_assets", "DOUBLE"),
    ("total_assets_prior", "DOUBLE"),
    ("current_assets", "DOUBLE"),
    ("current_assets_prior", "DOUBLE"),
    ("current_liabilities", "DOUBLE"),
    ("current_liabilities_prior", "DOUBLE"),
    ("long_term_debt", "DOUBLE"),
    ("long_term_debt_prior", "DOUBLE"),
    ("shares_outstanding", "DOUBLE"),
    ("shares_outstanding_prior", "DOUBLE"),
    ("invested_capital", "DOUBLE"),
)

SCORE_SCHEMA: tuple[tuple[str, str], ...] = (
    ("algorithm_slug", "VARCHAR"),
    ("algorithm_version", "VARCHAR"),
    ("security_id", "VARCHAR"),
    ("ticker", "VARCHAR"),
    ("eligible", "BOOLEAN"),
    ("score", "DOUBLE"),
    ("rank", "INTEGER"),
    ("reasons_json", "VARCHAR"),
    ("warnings_json", "VARCHAR"),
    ("metrics_used_json", "VARCHAR"),
)


class StorageLayout:
    def __init__(self, root: Path) -> None:
        self.root = root

    def raw_directory(self, retrieved_on: date, provider: str) -> Path:
        return (
            self.root
            / "data"
            / "raw"
            / retrieved_on.isoformat()
            / _safe_component(provider)
        )

    def normalized_directory(self, as_of_date: date) -> Path:
        return self.root / "data" / "normalized" / as_of_date.isoformat()

    def run_directory(self, run_id: str) -> Path:
        return self.root / "runs" / _safe_component(run_id)


class RawResponseCache:
    def __init__(self, layout: StorageLayout) -> None:
        self.layout = layout

    def read_json(
        self,
        *,
        provider: str,
        retrieved_on: date,
        key: str,
    ) -> Any | None:
        source = self._path(provider, retrieved_on, key)
        if not source.is_file():
            return None
        with gzip.open(source, "rt", encoding="utf-8") as input_file:
            return json.load(input_file)

    def write_json(
        self,
        *,
        provider: str,
        retrieved_on: date,
        key: str,
        payload: Mapping[str, Any] | Sequence[Any],
    ) -> Path:
        destination = self._path(provider, retrieved_on, key)
        directory = destination.parent
        directory.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".json.gz.tmp")
        with gzip.open(temporary, "wt", encoding="utf-8") as output_file:
            json.dump(payload, output_file, sort_keys=True, separators=(",", ":"))
        temporary.replace(destination)
        return destination

    def _path(self, provider: str, retrieved_on: date, key: str) -> Path:
        directory = self.layout.raw_directory(retrieved_on, provider)
        return directory / f"{_safe_component(key)}.json.gz"


class ParquetSnapshotStore:
    """Write canonical snapshots through DuckDB without requiring Pandas."""

    def write_screening_records(
        self, destination: Path, records: Sequence[ScreeningRecord]
    ) -> Path:
        rows = [
            tuple(getattr(record, column) for column, _ in SCREENING_RECORD_SCHEMA)
            for record in records
        ]
        self._write_rows(destination, SCREENING_RECORD_SCHEMA, rows)
        return destination

    def read_screening_records(self, source: Path) -> tuple[ScreeningRecord, ...]:
        duckdb = _load_duckdb()
        columns = ", ".join(column for column, _ in SCREENING_RECORD_SCHEMA)
        with duckdb.connect() as connection:
            rows = connection.execute(
                f"SELECT {columns} FROM read_parquet(?)", [str(source)]
            ).fetchall()
        return tuple(
            ScreeningRecord.from_dict(
                dict(zip((column for column, _ in SCREENING_RECORD_SCHEMA), row))
            )
            for row in rows
        )

    def write_scores(
        self, destination: Path, scores: Sequence[StockScore]
    ) -> Path:
        rows = [
            (
                score.algorithm_slug,
                score.algorithm_version,
                score.security_id,
                score.ticker,
                score.eligible,
                score.score,
                score.rank,
                json.dumps(score.reasons),
                json.dumps(score.warnings),
                json.dumps(score.metrics_used or {}, sort_keys=True),
            )
            for score in scores
        ]
        self._write_rows(destination, SCORE_SCHEMA, rows)
        return destination

    def _write_rows(
        self,
        destination: Path,
        schema: Sequence[tuple[str, str]],
        rows: Sequence[tuple[Any, ...]],
    ) -> None:
        duckdb = _load_duckdb()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        if temporary.exists():
            temporary.unlink()

        definitions = ", ".join(f"{name} {data_type}" for name, data_type in schema)
        placeholders = ", ".join("?" for _ in schema)
        escaped_path = str(temporary.resolve()).replace("'", "''")
        with duckdb.connect() as connection:
            connection.execute(f"CREATE TABLE snapshot ({definitions})")
            if rows:
                connection.executemany(
                    f"INSERT INTO snapshot VALUES ({placeholders})", rows
                )
            connection.execute(
                f"COPY snapshot TO '{escaped_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        temporary.replace(destination)


class RunArtifactStore:
    def __init__(self, layout: StorageLayout, parquet: ParquetSnapshotStore) -> None:
        self.layout = layout
        self.parquet = parquet

    def write(
        self,
        *,
        manifest: RunManifest,
        all_scores: Sequence[StockScore],
        shortlist: Sequence[StockScore],
    ) -> Path:
        run_directory = self.layout.run_directory(manifest.run_id)
        if run_directory.exists() and any(run_directory.iterdir()):
            raise FileExistsError(f"run directory already exists: {run_directory}")
        run_directory.mkdir(parents=True, exist_ok=True)

        self.parquet.write_scores(run_directory / "all_scores.parquet", all_scores)
        _write_json(run_directory / "manifest.json", asdict(manifest))
        self._write_shortlist(run_directory / "shortlist.csv", shortlist)
        return run_directory

    def _write_shortlist(
        self, destination: Path, shortlist: Sequence[StockScore]
    ) -> None:
        with destination.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(
                output_file,
                fieldnames=("ticker", "rank", "score", "reasons", "warnings"),
            )
            writer.writeheader()
            for score in shortlist:
                writer.writerow(
                    {
                        "ticker": score.ticker,
                        "rank": score.rank,
                        "score": score.score,
                        "reasons": " | ".join(score.reasons),
                        "warnings": " | ".join(score.warnings),
                    }
                )


def _load_duckdb():
    try:
        import duckdb
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "DuckDB is required for Parquet storage; run 'poetry install'"
        ) from error
    return duckdb


def _write_json(destination: Path, payload: Mapping[str, Any]) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as output_file:
        json.dump(
            payload,
            output_file,
            default=_json_default,
            indent=2,
            sort_keys=True,
        )
        output_file.write("\n")
    temporary.replace(destination)


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _safe_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    if not sanitized:
        raise ValueError("path component cannot be empty")
    return sanitized
