"""Strict, sourced import of dated market observations from CSV."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
import math
from pathlib import Path

from stocks_infer.research.models import MarketObservation, ResearchBundle, SourceDocument


MARKET_CSV_COLUMNS = (
    "ticker",
    "price_date",
    "available_at",
    "close",
    "currency",
    "adjustment",
    "shares_outstanding",
    "share_count_date",
    "price_source_id",
    "price_source_title",
    "price_source_url",
    "price_source_published_at",
    "price_source_retrieved_at",
    "share_source_id",
    "share_source_title",
    "share_source_url",
    "share_source_published_at",
    "share_source_retrieved_at",
)


def import_market_csv(
    bundle: ResearchBundle,
    path: Path,
    *,
    require_all: bool = False,
) -> ResearchBundle:
    """Return a new bundle containing strictly validated market CSV rows."""
    companies_by_ticker = {}
    for company in bundle.companies:
        ticker = company.ticker.upper()
        if ticker in companies_by_ticker:
            raise ValueError(f"duplicate company ticker in bundle: {ticker}")
        companies_by_ticker[ticker] = company

    sources = {source.source_id: source for source in bundle.sources}
    prices = list(bundle.prices)
    existing_keys = {
        (price.security_id, price.price_date, price.available_at, price.source_id)
        for price in prices
    }
    imported_tickers: set[str] = set()

    with path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = tuple(reader.fieldnames or ())
        if len(fieldnames) != len(set(fieldnames)) or set(fieldnames) != set(MARKET_CSV_COLUMNS):
            missing = sorted(set(MARKET_CSV_COLUMNS) - set(fieldnames))
            unknown = sorted(set(fieldnames) - set(MARKET_CSV_COLUMNS))
            raise ValueError(f"invalid market CSV columns; missing={missing}, unknown={unknown}")
        for row_number, raw in enumerate(reader, start=2):
            if None in raw:
                raise ValueError(f"market CSV row {row_number}: too many fields")
            row = {key: (value or "").strip() for key, value in raw.items()}
            if not any(row.values()):
                continue
            ticker = row["ticker"].upper()
            company = companies_by_ticker.get(ticker)
            if company is None:
                raise ValueError(f"market CSV row {row_number}: unknown ticker {ticker or '<blank>'}")
            imported_tickers.add(ticker)

            price_source = _source_from_row(row, row_number, "price")
            _merge_source(sources, price_source, row_number)
            if row["share_source_id"]:
                share_source = _source_from_row(row, row_number, "share")
                _merge_source(sources, share_source, row_number)
            else:
                share_fields = tuple(
                    name for name in MARKET_CSV_COLUMNS
                    if name.startswith("share_source_") and name != "share_source_id"
                )
                if any(row[name] for name in share_fields):
                    raise ValueError(
                        f"market CSV row {row_number}: share-source metadata requires share_source_id"
                    )
                share_source = price_source

            try:
                observation = MarketObservation(
                    security_id=company.security_id,
                    price_date=date.fromisoformat(row["price_date"]),
                    available_at=date.fromisoformat(row["available_at"]),
                    close=_positive_number(row["close"], "close"),
                    shares_outstanding=_positive_number(row["shares_outstanding"], "shares_outstanding"),
                    currency=row["currency"],
                    source_id=price_source.source_id,
                    share_source_id=(
                        share_source.source_id if share_source.source_id != price_source.source_id else None
                    ),
                    share_count_date=date.fromisoformat(row["share_count_date"]),
                    adjustment=row["adjustment"],
                )
            except ValueError as error:
                raise ValueError(f"market CSV row {row_number}: {error}") from error
            if observation.currency != company.currency:
                raise ValueError(
                    f"market CSV row {row_number}: {ticker} uses {company.currency}, not {observation.currency}"
                )
            source_ids = (observation.source_id, observation.effective_share_source_id)
            if any(sources[source_id].published_at > observation.available_at for source_id in source_ids):
                raise ValueError(
                    f"market CSV row {row_number}: observation predates a supporting source"
                )
            key = (
                observation.security_id,
                observation.price_date,
                observation.available_at,
                observation.source_id,
            )
            if key in existing_keys:
                raise ValueError(
                    f"market CSV row {row_number}: duplicate observation identity for {ticker}"
                )
            existing_keys.add(key)
            prices.append(observation)

    if not imported_tickers:
        raise ValueError("market CSV contains no observations")
    if require_all:
        missing = sorted(set(companies_by_ticker) - imported_tickers)
        if missing:
            raise ValueError("market CSV is missing required tickers: " + ", ".join(missing))

    return replace(
        bundle,
        sources=tuple(sorted(sources.values(), key=lambda source: source.source_id)),
        prices=tuple(sorted(
            prices,
            key=lambda price: (
                price.security_id,
                price.price_date,
                price.available_at,
                price.source_id,
                price.effective_share_source_id,
            ),
        )),
    )


def _source_from_row(row: dict[str, str], row_number: int, prefix: str) -> SourceDocument:
    required = (
        f"{prefix}_source_id",
        f"{prefix}_source_title",
        f"{prefix}_source_url",
        f"{prefix}_source_published_at",
        f"{prefix}_source_retrieved_at",
    )
    missing = [name for name in required if not row[name]]
    if missing:
        raise ValueError(f"market CSV row {row_number}: missing {', '.join(missing)}")
    url = row[f"{prefix}_source_url"]
    if not url.startswith("https://"):
        raise ValueError(f"market CSV row {row_number}: source URL must use https")
    try:
        return SourceDocument(
            source_id=row[f"{prefix}_source_id"],
            title=row[f"{prefix}_source_title"],
            url=url,
            published_at=date.fromisoformat(row[f"{prefix}_source_published_at"]),
            retrieved_at=date.fromisoformat(row[f"{prefix}_source_retrieved_at"]),
        )
    except ValueError as error:
        raise ValueError(f"market CSV row {row_number}: invalid {prefix} source: {error}") from error


def _merge_source(
    sources: dict[str, SourceDocument],
    source: SourceDocument,
    row_number: int,
) -> None:
    existing = sources.get(source.source_id)
    if existing is not None and not _same_source(existing, source):
        raise ValueError(
            f"market CSV row {row_number}: inconsistent metadata for source {source.source_id}"
        )
    if existing is None:
        sources[source.source_id] = source


def _same_source(left: SourceDocument, right: SourceDocument) -> bool:
    """Compare CSV source metadata while preserving an existing accession."""
    return (
        left.source_id == right.source_id
        and left.title == right.title
        and left.url == right.url
        and left.published_at == right.published_at
        and left.retrieved_at == right.retrieved_at
        and (
            left.accession == right.accession
            or left.accession is None
            or right.accession is None
        )
    )


def _positive_number(raw: str, label: str) -> float:
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{label} must be numeric") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return value
