"""Twelve Data price adapter with SEC outstanding-share provenance."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
import math
from pathlib import Path
from typing import Callable, Mapping

from stocks_infer.research import MARKET_ADAPTER_VERSION
from stocks_infer.research.market_csv import MARKET_CSV_COLUMNS
from stocks_infer.research.models import Company, ResearchBundle, SourceDocument
from stocks_infer.research.twelve_data import TwelveDataClient, TwelveDataError
from stocks_infer.storage import RawResponseCache


TWELVE_DATA_ADAPTER_VERSION = MARKET_ADAPTER_VERSION
SEC_OUTSTANDING_SHARES_CONCEPT = "EntityCommonStockSharesOutstanding"


@dataclass(frozen=True)
class ReviewedTwelveDataSecurity:
    provider_symbol: str
    exchange: str
    mic_code: str
    instrument_type: str = "Common Stock"


# Identity metadata reconciled in the 30-company coverage trial. Exact MICs
# distinguish the Nasdaq Global, Capital, and NYSE venues. TPC's qualified
# symbol avoids an ambiguous bare-symbol lookup.
TWELVE_DATA_SECURITIES: Mapping[str, ReviewedTwelveDataSecurity] = {
    "ABR": ReviewedTwelveDataSecurity("ABR", "NYSE", "XNYS", "REIT"),
    "AMAT": ReviewedTwelveDataSecurity("AMAT", "NASDAQ", "XNGS"),
    "AMGN": ReviewedTwelveDataSecurity("AMGN", "NASDAQ", "XNGS"),
    "AMTM": ReviewedTwelveDataSecurity("AMTM", "NYSE", "XNYS"),
    "ANDE": ReviewedTwelveDataSecurity("ANDE", "NASDAQ", "XNGS"),
    "BWA": ReviewedTwelveDataSecurity("BWA", "NYSE", "XNYS"),
    "CAT": ReviewedTwelveDataSecurity("CAT", "NYSE", "XNYS"),
    "CMS": ReviewedTwelveDataSecurity("CMS", "NYSE", "XNYS"),
    "COF": ReviewedTwelveDataSecurity("COF", "NYSE", "XNYS"),
    "COHR": ReviewedTwelveDataSecurity("COHR", "NYSE", "XNYS"),
    "COKE": ReviewedTwelveDataSecurity("COKE", "NASDAQ", "XNGS"),
    "CW": ReviewedTwelveDataSecurity("CW", "NYSE", "XNYS"),
    "DUOL": ReviewedTwelveDataSecurity("DUOL", "NASDAQ", "XNGS"),
    "EPR": ReviewedTwelveDataSecurity("EPR", "NYSE", "XNYS", "REIT"),
    "ESAB": ReviewedTwelveDataSecurity("ESAB", "NYSE", "XNYS"),
    "FHN": ReviewedTwelveDataSecurity("FHN", "NYSE", "XNYS"),
    "INTU": ReviewedTwelveDataSecurity("INTU", "NASDAQ", "XNGS"),
    "M": ReviewedTwelveDataSecurity("M", "NYSE", "XNYS"),
    "MD": ReviewedTwelveDataSecurity("MD", "NYSE", "XNYS"),
    "NAVI": ReviewedTwelveDataSecurity("NAVI", "NASDAQ", "XNGS"),
    "NEO": ReviewedTwelveDataSecurity("NEO", "NASDAQ", "XNCM"),
    "OC": ReviewedTwelveDataSecurity("OC", "NYSE", "XNYS"),
    "PECO": ReviewedTwelveDataSecurity("PECO", "NASDAQ", "XNGS", "REIT"),
    "QCOM": ReviewedTwelveDataSecurity("QCOM", "NASDAQ", "XNGS"),
    "ROAD": ReviewedTwelveDataSecurity("ROAD", "NASDAQ", "XNGS"),
    "SEI": ReviewedTwelveDataSecurity("SEI", "NYSE", "XNYS"),
    "TPC": ReviewedTwelveDataSecurity("TPC:NYSE", "NYSE", "XNYS"),
    "UTHR": ReviewedTwelveDataSecurity("UTHR", "NASDAQ", "XNGS"),
    "VTR": ReviewedTwelveDataSecurity("VTR", "NYSE", "XNYS", "REIT"),
    "WSM": ReviewedTwelveDataSecurity("WSM", "NYSE", "XNYS"),
}


@dataclass(frozen=True)
class ReviewedShareCount:
    share_count_date: date
    shares_outstanding: int
    filed: date
    accession: str
    form: str
    description: str


# Company Facts drops the dimensional cover-page facts for these multi-class
# issuers. Values are the sum of the listed common classes in the exact filing.
# The adapter admits an entry only when that accession is present in the saved
# Company Facts payload, so a reviewed value cannot float free of local input.
REVIEWED_SHARE_COUNTS: Mapping[str, tuple[ReviewedShareCount, ...]] = {
    "COKE": (
        ReviewedShareCount(
            date(2026, 7, 24), 66_564_294, date(2026, 8, 5),
            "0001628280-26-053370", "10-Q",
            "56,517,334 Common plus 10,046,960 Class B shares",
        ),
    ),
    "DUOL": (
        ReviewedShareCount(
            date(2026, 8, 4), 46_786_269, date(2026, 8, 6),
            "0001628280-26-053603", "10-Q",
            "40,387,012 Class A plus 6,399,257 Class B shares",
        ),
    ),
    "ROAD": (
        ReviewedShareCount(
            date(2026, 8, 5), 56_755_555, date(2026, 8, 7),
            "0001628280-26-054661", "10-Q",
            "48,206,437 Class A plus 8,549,118 Class B shares",
        ),
    ),
    "SEI": (
        ReviewedShareCount(
            date(2026, 8, 3), 76_566_392, date(2026, 8, 6),
            "0001628280-26-054349", "10-Q",
            "65,831,540 Class A plus 10,734,852 Class B shares",
        ),
    ),
}


@dataclass(frozen=True)
class SecOutstandingShares:
    value: int
    share_count_date: date
    source: SourceDocument
    source_concept: str


def build_twelve_data_market_rows(
    bundle: ResearchBundle,
    companyfacts_by_ticker: Mapping[str, dict],
    client: TwelveDataClient,
    *,
    as_of: date,
    retrieved_on: date,
    raw_cache: RawResponseCache | None = None,
    lookback_days: int = 14,
    on_result: Callable[[int, int, str, date], None] | None = None,
) -> tuple[dict[str, str], ...]:
    """Build strict market CSV rows from unadjusted closes and SEC shares."""
    if retrieved_on < as_of:
        raise ValueError("market-data retrieval date cannot precede the cutoff")
    if lookback_days < 7:
        raise ValueError("market-data lookback must be at least seven days")

    companies = tuple(sorted(bundle.companies, key=lambda item: item.ticker))
    sources = {source.source_id: source for source in bundle.sources}
    missing_payloads = sorted(
        company.ticker for company in companies
        if company.ticker not in companyfacts_by_ticker
    )
    if missing_payloads:
        raise ValueError(
            "missing SEC Company Facts payloads: " + ", ".join(missing_payloads)
        )

    start_date = as_of - timedelta(days=lookback_days)
    rows: list[dict[str, str]] = []
    for index, company in enumerate(companies, start=1):
        security = TWELVE_DATA_SECURITIES.get(company.ticker)
        if security is None:
            raise ValueError(
                f"no reviewed Twelve Data security identity for {company.ticker}"
            )
        provider_symbol = security.provider_symbol
        cache_key = (
            f"{company.ticker}-daily-unadjusted-"
            f"{start_date.isoformat()}-{as_of.isoformat()}"
        )
        cached = (
            raw_cache.read_json(
                provider="twelve-data",
                retrieved_on=retrieved_on,
                key=cache_key,
            )
            if raw_cache is not None
            else None
        )
        if cached is None:
            payload, source_url = client.daily_time_series(
                provider_symbol, start_date, as_of
            )
        else:
            if (
                not isinstance(cached, dict)
                or cached.get("adapter_version") != TWELVE_DATA_ADAPTER_VERSION
                or not isinstance(cached.get("request_url"), str)
                or not isinstance(cached.get("response"), dict)
            ):
                raise ValueError(
                    f"invalid cached Twelve Data response for {company.ticker}"
                )
            source_url = cached["request_url"]
            payload = cached["response"]
        if not source_url.startswith("https://") or "apikey" in source_url.lower():
            raise ValueError(
                f"unsafe Twelve Data source URL for {company.ticker}"
            )
        if raw_cache is not None and cached is None:
            raw_cache.write_json(
                provider="twelve-data",
                retrieved_on=retrieved_on,
                key=cache_key,
                payload={
                    "adapter_version": TWELVE_DATA_ADAPTER_VERSION,
                    "request_url": source_url,
                    "response": payload,
                },
            )
        price_date, close = _latest_unadjusted_close(
            company, security, payload, as_of
        )
        shares = select_sec_outstanding_shares(
            company,
            companyfacts_by_ticker[company.ticker],
            price_date=price_date,
            available_on=as_of,
            sources=sources,
            retrieved_on=retrieved_on,
        )
        price_source_id = (
            f"twelve-data:{provider_symbol}:daily-unadjusted:"
            f"{start_date.isoformat()}:{as_of.isoformat()}:"
            f"retrieved-{retrieved_on.isoformat()}"
        )
        available_at = max(price_date, shares.source.published_at)
        rows.append({
            "ticker": company.ticker,
            "price_date": price_date.isoformat(),
            "available_at": available_at.isoformat(),
            "close": format(close, ".15g"),
            "currency": company.currency,
            "adjustment": "unadjusted",
            "shares_outstanding": str(shares.value),
            "share_count_date": shares.share_count_date.isoformat(),
            "price_source_id": price_source_id,
            "price_source_title": (
                f"Twelve Data unadjusted daily close for {provider_symbol} "
                f"on {price_date.isoformat()}"
            ),
            "price_source_url": source_url,
            "price_source_published_at": price_date.isoformat(),
            "price_source_retrieved_at": retrieved_on.isoformat(),
            "share_source_id": shares.source.source_id,
            "share_source_title": shares.source.title,
            "share_source_url": shares.source.url,
            "share_source_published_at": shares.source.published_at.isoformat(),
            "share_source_retrieved_at": shares.source.retrieved_at.isoformat(),
        })
        if on_result is not None:
            on_result(index, len(companies), company.ticker, price_date)
    return tuple(rows)


def write_twelve_data_market_csv(
    output: Path, rows: tuple[dict[str, str], ...]
) -> Path:
    """Write adapter rows without replacing an existing snapshot."""
    if output.exists():
        raise FileExistsError(f"Twelve Data market CSV already exists: {output}")
    if not rows:
        raise ValueError("Twelve Data market adapter produced no rows")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=MARKET_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return output


def load_companyfacts_directory(
    directory: Path, companies: tuple[Company, ...]
) -> dict[str, dict]:
    """Load one saved SEC Company Facts response per bundle company."""
    import json

    payloads = {}
    for company in companies:
        path = directory / f"{company.ticker}-companyfacts.json"
        if not path.is_file():
            raise FileNotFoundError(f"missing SEC Company Facts file: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"SEC Company Facts payload is not an object: {path}")
        payloads[company.ticker] = payload
    return payloads


def select_sec_outstanding_shares(
    company: Company,
    payload: dict,
    *,
    price_date: date,
    available_on: date,
    sources: Mapping[str, SourceDocument],
    retrieved_on: date,
) -> SecOutstandingShares:
    """Select a dated SEC cover-page count without EPS-share substitution."""
    cik = _company_cik(company)
    if int(payload.get("cik", -1)) != cik:
        raise ValueError(f"SEC CIK mismatch for {company.ticker}")

    candidates: list[tuple[date, date, str, int, str, str]] = []
    facts = (
        payload.get("facts", {})
        .get("dei", {})
        .get(SEC_OUTSTANDING_SHARES_CONCEPT, {})
        .get("units", {})
        .get("shares", [])
    )
    for raw in facts:
        if raw.get("form") not in {"10-K", "10-K/A", "10-Q", "10-Q/A"}:
            continue
        try:
            end = date.fromisoformat(raw["end"])
            filed = date.fromisoformat(raw["filed"])
            accession = str(raw["accn"])
            value = _whole_positive_shares(raw["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if end <= price_date and filed <= available_on:
            candidates.append((
                end, filed, accession, value, str(raw["form"]),
                f"dei:{SEC_OUTSTANDING_SHARES_CONCEPT}",
            ))

    for reviewed in REVIEWED_SHARE_COUNTS.get(company.ticker, ()):
        if (
            reviewed.share_count_date <= price_date
            and reviewed.filed <= available_on
            and _filing_is_present(payload, reviewed)
        ):
            candidates.append((
                reviewed.share_count_date,
                reviewed.filed,
                reviewed.accession,
                reviewed.shares_outstanding,
                reviewed.form,
                f"reviewed-cover-page:{reviewed.description}",
            ))

    if not candidates:
        raise ValueError(
            f"no usable SEC outstanding-share count for {company.ticker} "
            f"on or before {price_date.isoformat()}"
        )
    newest_key = max((item[0], item[1]) for item in candidates)
    newest = [item for item in candidates if (item[0], item[1]) == newest_key]
    identities = {(item[2], item[3], item[4], item[5]) for item in newest}
    if len(identities) != 1:
        raise ValueError(
            f"ambiguous SEC outstanding-share count for {company.ticker} "
            f"at {newest_key[0].isoformat()}"
        )
    end, filed, accession, value, form, concept = newest[0]
    source_id = f"sec:{accession}"
    source = sources.get(source_id)
    if source is None:
        source = SourceDocument(
            source_id=source_id,
            title=f"SEC Form {form.replace('/A', '')} {accession} for {company.ticker}",
            url=(
                "https://www.sec.gov/Archives/edgar/data/"
                f"{cik}/{accession.replace('-', '')}/{accession}-index.htm"
            ),
            published_at=filed,
            retrieved_at=retrieved_on,
            accession=accession,
        )
    elif source.published_at != filed:
        raise ValueError(
            f"SEC source date mismatch for {company.ticker} accession {accession}"
        )
    return SecOutstandingShares(value, end, source, concept)


def _latest_unadjusted_close(
    company: Company,
    security: ReviewedTwelveDataSecurity,
    payload: dict,
    as_of: date,
) -> tuple[date, float]:
    if not isinstance(payload, dict):
        raise TwelveDataError("time-series response is not a JSON object")
    if payload.get("status") == "error":
        raise TwelveDataError(str(payload.get("message") or "unknown API error"))
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        raise TwelveDataError("time-series response lacks metadata")
    provider_symbol = security.provider_symbol
    returned_symbol = str(meta.get("symbol") or "").upper()
    accepted_symbols = {company.ticker.upper(), provider_symbol.upper()}
    if returned_symbol not in accepted_symbols:
        raise TwelveDataError(
            f"expected {company.ticker}, received symbol {returned_symbol or '<blank>'}"
        )
    returned_currency = str(meta.get("currency") or "").upper()
    if returned_currency != company.currency.upper():
        raise TwelveDataError(
            f"expected {company.currency}, received currency "
            f"{returned_currency or '<blank>'}"
        )
    returned_exchange = str(meta.get("exchange") or "").upper()
    if returned_exchange != security.exchange:
        raise TwelveDataError(
            f"expected exchange {security.exchange}, received "
            f"{returned_exchange or '<blank>'}"
        )
    returned_mic = str(meta.get("mic_code") or "").upper()
    if returned_mic != security.mic_code:
        raise TwelveDataError(
            f"expected MIC {security.mic_code}, received "
            f"{returned_mic or '<blank>'}"
        )
    returned_type = str(meta.get("type") or "")
    if returned_type != security.instrument_type:
        raise TwelveDataError(
            f"expected instrument type {security.instrument_type}, received "
            f"{returned_type or '<blank>'}"
        )
    values = payload.get("values")
    if not isinstance(values, list) or not values:
        raise TwelveDataError(f"no daily prices returned for {provider_symbol}")
    observations: list[tuple[date, float, float | None]] = []
    for raw in values:
        if not isinstance(raw, dict):
            raise TwelveDataError("time-series observation is not an object")
        try:
            observed_on = date.fromisoformat(str(raw["datetime"]))
            close = float(raw["close"])
        except (KeyError, TypeError, ValueError) as error:
            raise TwelveDataError("time-series observation has invalid date or close") from error
        if not math.isfinite(close) or close <= 0:
            raise TwelveDataError("time-series observation has invalid close")
        try:
            volume = float(raw["volume"]) if raw.get("volume") is not None else None
        except (TypeError, ValueError) as error:
            raise TwelveDataError("time-series observation has invalid volume") from error
        if volume is not None and (not math.isfinite(volume) or volume < 0):
            raise TwelveDataError("time-series observation has invalid volume")
        if observed_on <= as_of:
            observations.append((observed_on, close, volume))
    if not observations:
        raise TwelveDataError(
            f"no daily price on or before cutoff {as_of.isoformat()}"
        )
    latest_date = max(item[0] for item in observations)
    latest_observations = [item for item in observations if item[0] == latest_date]
    latest_values = {item[1] for item in latest_observations}
    if len(latest_values) != 1:
        raise TwelveDataError(
            f"conflicting closes returned for {latest_date.isoformat()}"
        )
    if any(item[2] is None or item[2] <= 0 for item in latest_observations):
        raise TwelveDataError(
            f"latest close has missing or zero volume on {latest_date.isoformat()}"
        )
    return latest_date, latest_values.pop()


def _company_cik(company: Company) -> int:
    prefix, separator, raw = company.security_id.partition(":")
    if prefix != "cik" or not separator or not raw.isdigit():
        raise ValueError(
            f"{company.ticker} security_id must be a canonical cik identifier"
        )
    return int(raw)


def _whole_positive_shares(raw: object) -> int:
    if isinstance(raw, bool):
        raise ValueError("share count must be numeric")
    value = float(raw)
    if not math.isfinite(value) or value <= 0 or not value.is_integer():
        raise ValueError("share count must be a positive whole number")
    return int(value)


def _filing_is_present(payload: dict, reviewed: ReviewedShareCount) -> bool:
    for taxonomy in payload.get("facts", {}).values():
        if not isinstance(taxonomy, dict):
            continue
        for concept in taxonomy.values():
            for observations in concept.get("units", {}).values():
                if any(
                    raw.get("accn") == reviewed.accession
                    and raw.get("filed") == reviewed.filed.isoformat()
                    and raw.get("form") == reviewed.form
                    for raw in observations
                    if isinstance(raw, dict)
                ):
                    return True
    return False
