"""Coverage probe for Twelve Data's daily time-series API."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, replace
from datetime import date
import json
import math
import os
from pathlib import Path
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from stocks_infer.research.models import Company, ResearchBundle


TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
TWELVE_DATA_API_KEY_ENV = "TWELVE_DATA_API_KEY"


class TwelveDataError(RuntimeError):
    """A safe, credential-free description of a Twelve Data failure."""


def load_twelve_data_api_key(env_file: Path = Path(".env")) -> str:
    """Load the API key from the process environment or a gitignored .env file."""
    environment_value = os.getenv(TWELVE_DATA_API_KEY_ENV, "").strip()
    if environment_value:
        return environment_value
    if not env_file.is_file():
        return ""
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == TWELVE_DATA_API_KEY_ENV:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value.strip()
    return ""


@dataclass(frozen=True)
class TwelveDataCoverage:
    ticker: str
    company_name: str
    security_id: str
    expected_currency: str
    status: str
    returned_symbol: str
    exchange: str
    mic_code: str
    returned_currency: str
    instrument_type: str
    observation_count: int
    missing_volume_count: int
    zero_volume_count: int
    zero_volume_percent: float
    longest_flat_close_run: int
    longest_flat_close_start: str
    longest_flat_close_end: str
    earliest_date: str
    latest_date: str
    history_years: float
    latest_close: float | None
    requested_start: str
    requested_end: str
    requested_adjustment: str
    issues: str
    source_url: str


class TwelveDataClient:
    """Small standard-library client with a conservative rolling rate limit."""

    def __init__(
        self,
        api_key: str,
        *,
        requests_per_minute: int = 8,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Twelve Data API key is required")
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive")
        self._api_key = api_key
        self._requests_per_minute = requests_per_minute
        self._sleeper = sleeper
        self._clock = clock
        self._request_times: list[float] = []

    def daily_time_series(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> tuple[dict, str]:
        params = {
            "symbol": ticker,
            "interval": "1day",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "adjust": "none",
            "order": "ASC",
            "format": "JSON",
        }
        source_url = f"{TWELVE_DATA_BASE_URL}/time_series?{urlencode(params)}"
        self._wait_for_capacity()
        request = Request(
            source_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"apikey {self._api_key}",
                "User-Agent": "stocks-infer/0.1 Twelve-Data-client",
            },
        )
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            message = _http_error_message(error)
            raise TwelveDataError(f"HTTP {error.code}: {message}") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise TwelveDataError(f"request failed: {error}") from error
        if not isinstance(payload, dict):
            raise TwelveDataError("response is not a JSON object")
        if payload.get("status") == "error":
            raise TwelveDataError(str(payload.get("message") or "unknown API error"))
        return payload, source_url

    def resolve_exchange_symbol(self, company: Company) -> str | None:
        """Resolve an ambiguous bare ticker to a primary US exchange symbol."""
        params = {"symbol": company.ticker, "outputsize": "20"}
        source_url = f"{TWELVE_DATA_BASE_URL}/symbol_search?{urlencode(params)}"
        self._wait_for_capacity()
        request = Request(
            source_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"apikey {self._api_key}",
                "User-Agent": "stocks-infer/0.1 Twelve-Data-client",
            },
        )
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            message = _http_error_message(error)
            raise TwelveDataError(f"symbol search HTTP {error.code}: {message}") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise TwelveDataError(f"symbol search failed: {error}") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise TwelveDataError("symbol search response lacks data")
        candidates = [
            item for item in payload["data"]
            if isinstance(item, dict)
            and str(item.get("symbol") or "").upper() == company.ticker.upper()
            and str(item.get("currency") or "").upper() == company.currency.upper()
            and str(item.get("instrument_type") or "") == "Common Stock"
        ]
        candidates.sort(key=lambda item: (
            str(item.get("country") or "") != "United States",
            str(item.get("mic_code") or "") == "IEXG",
            str(item.get("exchange") or ""),
        ))
        if not candidates:
            return None
        exchange = str(candidates[0].get("exchange") or "").strip()
        return f"{company.ticker}:{exchange}" if exchange else None

    def _wait_for_capacity(self) -> None:
        now = self._clock()
        self._request_times = [stamp for stamp in self._request_times if now - stamp < 60]
        if len(self._request_times) >= self._requests_per_minute:
            wait_for = 60 - (now - self._request_times[0]) + 0.05
            self._sleeper(max(wait_for, 0))
            now = self._clock()
            self._request_times = [stamp for stamp in self._request_times if now - stamp < 60]
        self._request_times.append(self._clock())


def probe_twelve_data_coverage(
    bundle: ResearchBundle,
    client: TwelveDataClient,
    *,
    start_date: date,
    end_date: date,
    on_result: Callable[[int, int, TwelveDataCoverage], None] | None = None,
) -> tuple[TwelveDataCoverage, ...]:
    """Probe every company in a bundle without aborting on one-symbol failures."""
    if start_date >= end_date:
        raise ValueError("coverage start date must precede end date")
    companies = tuple(sorted(bundle.companies, key=lambda company: company.ticker))
    results = []
    for index, company in enumerate(companies, start=1):
        provider_symbol = company.ticker
        try:
            payload, source_url = client.daily_time_series(
                provider_symbol, start_date, end_date
            )
        except TwelveDataError as error:
            if "No data is available" not in str(error):
                result = _error_result(company, str(error), start_date, end_date)
            else:
                try:
                    provider_symbol = client.resolve_exchange_symbol(company)
                    if provider_symbol is None:
                        raise TwelveDataError("no matching exchange-qualified symbol")
                    payload, source_url = client.daily_time_series(
                        provider_symbol, start_date, end_date
                    )
                except TwelveDataError as retry_error:
                    result = _error_result(
                        company,
                        f"{error}; exchange-qualified retry failed: {retry_error}",
                        start_date,
                        end_date,
                    )
                else:
                    result = _analyze_payload(
                        company, payload, source_url, start_date, end_date
                    )
                    note = f"required exchange-qualified symbol {provider_symbol}"
                    result = replace(
                        result,
                        status="warning",
                        issues="; ".join(filter(None, (result.issues, note))),
                    )
        else:
            result = _analyze_payload(
                company, payload, source_url, start_date, end_date
            )
        results.append(result)
        if on_result is not None:
            on_result(index, len(companies), result)
    return tuple(results)


def write_twelve_data_coverage(
    output: Path,
    results: tuple[TwelveDataCoverage, ...],
    *,
    retrieved_at: date,
) -> Path:
    """Write detailed CSV plus a small sibling JSON summary."""
    summary_path = output.with_suffix(".summary.json")
    if output.exists() or summary_path.exists():
        raise FileExistsError(f"Twelve Data coverage output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=tuple(TwelveDataCoverage.__dataclass_fields__),
        )
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("covered", "warning", "error")
    }
    summary = {
        "provider": "Twelve Data",
        "endpoint": f"{TWELVE_DATA_BASE_URL}/time_series",
        "retrieved_at": retrieved_at.isoformat(),
        "requested_adjustment": "none",
        "company_count": len(results),
        "status_counts": counts,
        "all_tickers_covered": counts["error"] == 0,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary_path


def _analyze_payload(
    company: Company,
    payload: dict,
    source_url: str,
    start_date: date,
    end_date: date,
) -> TwelveDataCoverage:
    meta = payload.get("meta")
    values = payload.get("values")
    if not isinstance(meta, dict) or not isinstance(values, list) or not values:
        raise TwelveDataError("response lacks non-empty meta and values")
    observations: list[tuple[date, float, float | None]] = []
    for item in values:
        if not isinstance(item, dict):
            raise TwelveDataError("time-series value is not an object")
        try:
            observed_on = date.fromisoformat(str(item["datetime"])[:10])
            close = float(item["close"])
        except (KeyError, TypeError, ValueError) as error:
            raise TwelveDataError("time-series value has an invalid date or close") from error
        if not math.isfinite(close) or close <= 0:
            raise TwelveDataError("time-series value has a nonpositive or nonfinite close")
        if observed_on < start_date or observed_on > end_date:
            raise TwelveDataError("time-series value falls outside the requested dates")
        raw_volume = item.get("volume")
        volume = None if raw_volume in (None, "") else _nonnegative_number(
            raw_volume, "volume"
        )
        observations.append((observed_on, close, volume))
    if len({observed_on for observed_on, _, _ in observations}) != len(observations):
        raise TwelveDataError("time series contains duplicate dates")
    observations.sort()
    earliest, latest = observations[0], observations[-1]
    returned_symbol = str(meta.get("symbol") or "")
    returned_currency = str(meta.get("currency") or "").upper()
    issues = []
    if returned_symbol.upper() != company.ticker.upper():
        issues.append(f"returned symbol {returned_symbol or '<blank>'}")
    if returned_currency != company.currency.upper():
        issues.append(
            f"currency {returned_currency or '<blank>'} != {company.currency.upper()}"
        )
    if (end_date - latest[0]).days > 7:
        issues.append(f"latest observation is {(end_date - latest[0]).days} days old")
    if (earliest[0] - start_date).days > 7:
        issues.append("history begins after requested start; verify listing date")
    missing_volume_count = sum(volume is None for _, _, volume in observations)
    zero_volume_count = sum(volume == 0 for _, _, volume in observations)
    zero_volume_percent = round(100 * zero_volume_count / len(observations), 2)
    flat_run, flat_start, flat_end = _longest_flat_close_run(observations)
    if missing_volume_count:
        issues.append(f"{missing_volume_count} observations lack volume")
    if zero_volume_count >= 5 and zero_volume_percent >= 1:
        issues.append(
            f"{zero_volume_count} zero-volume observations ({zero_volume_percent}%)"
        )
    if flat_run >= 10:
        issues.append(
            f"close is unchanged for {flat_run} observations from "
            f"{flat_start.isoformat()} to {flat_end.isoformat()}"
        )
    status = "warning" if issues else "covered"
    history_years = round((latest[0] - earliest[0]).days / 365.2425, 2)
    return TwelveDataCoverage(
        ticker=company.ticker,
        company_name=company.name,
        security_id=company.security_id,
        expected_currency=company.currency,
        status=status,
        returned_symbol=returned_symbol,
        exchange=str(meta.get("exchange") or ""),
        mic_code=str(meta.get("mic_code") or ""),
        returned_currency=returned_currency,
        instrument_type=str(meta.get("type") or ""),
        observation_count=len(observations),
        missing_volume_count=missing_volume_count,
        zero_volume_count=zero_volume_count,
        zero_volume_percent=zero_volume_percent,
        longest_flat_close_run=flat_run,
        longest_flat_close_start=flat_start.isoformat(),
        longest_flat_close_end=flat_end.isoformat(),
        earliest_date=earliest[0].isoformat(),
        latest_date=latest[0].isoformat(),
        history_years=history_years,
        latest_close=latest[1],
        requested_start=start_date.isoformat(),
        requested_end=end_date.isoformat(),
        requested_adjustment="none",
        issues="; ".join(issues),
        source_url=source_url,
    )


def _error_result(
    company: Company,
    message: str,
    start_date: date,
    end_date: date,
) -> TwelveDataCoverage:
    return TwelveDataCoverage(
        ticker=company.ticker,
        company_name=company.name,
        security_id=company.security_id,
        expected_currency=company.currency,
        status="error",
        returned_symbol="",
        exchange="",
        mic_code="",
        returned_currency="",
        instrument_type="",
        observation_count=0,
        missing_volume_count=0,
        zero_volume_count=0,
        zero_volume_percent=0,
        longest_flat_close_run=0,
        longest_flat_close_start="",
        longest_flat_close_end="",
        earliest_date="",
        latest_date="",
        history_years=0,
        latest_close=None,
        requested_start=start_date.isoformat(),
        requested_end=end_date.isoformat(),
        requested_adjustment="none",
        issues=message,
        source_url="",
    )


def _http_error_message(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return error.reason or "request rejected"
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("status") or error.reason)
    return error.reason or "request rejected"


def _nonnegative_number(raw, label: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise TwelveDataError(f"time-series value has invalid {label}") from error
    if not math.isfinite(value) or value < 0:
        raise TwelveDataError(f"time-series value has invalid {label}")
    return value


def _longest_flat_close_run(
    observations: list[tuple[date, float, float | None]],
) -> tuple[int, date, date]:
    best_count = current_count = 1
    best_start = best_end = current_start = observations[0][0]
    previous_close = observations[0][1]
    for observed_on, close, _ in observations[1:]:
        if close == previous_close:
            current_count += 1
        else:
            current_count = 1
            current_start = observed_on
        if current_count > best_count:
            best_count = current_count
            best_start = current_start
            best_end = observed_on
        previous_close = close
    return best_count, best_start, best_end
