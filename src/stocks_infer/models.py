"""Canonical data exchanged between providers, storage, and algorithms."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Security:
    """A tradable listing with stable identifiers where available."""

    security_id: str
    ticker: str
    name: str
    exchange: str
    security_type: str = "common_stock"
    active: bool = True
    cik: str | None = None
    figi: str | None = None
    sector: str | None = None
    industry: str | None = None

    def __post_init__(self) -> None:
        if not self.security_id.strip():
            raise ValueError("security_id cannot be empty")
        if not self.ticker.strip():
            raise ValueError("ticker cannot be empty")


@dataclass(frozen=True, slots=True)
class FinancialSnapshot:
    """Normalized current and prior-period fundamentals known at an as-of date."""

    security_id: str
    as_of_date: date
    period_end: date
    available_at: date
    source: str
    currency: str = "USD"
    revenue_ttm: float | None = None
    revenue_prior_ttm: float | None = None
    gross_profit_ttm: float | None = None
    gross_profit_prior_ttm: float | None = None
    ebit_ttm: float | None = None
    net_income_ttm: float | None = None
    net_income_prior_ttm: float | None = None
    operating_cash_flow_ttm: float | None = None
    operating_cash_flow_prior_ttm: float | None = None
    free_cash_flow_ttm: float | None = None
    free_cash_flow_prior_ttm: float | None = None
    total_assets: float | None = None
    total_assets_prior: float | None = None
    current_assets: float | None = None
    current_assets_prior: float | None = None
    current_liabilities: float | None = None
    current_liabilities_prior: float | None = None
    long_term_debt: float | None = None
    long_term_debt_prior: float | None = None
    shares_outstanding: float | None = None
    shares_outstanding_prior: float | None = None
    invested_capital: float | None = None

    def __post_init__(self) -> None:
        if self.available_at > self.as_of_date:
            raise ValueError("financial data cannot be available after the as-of date")


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    """End-of-day market values used by fundamental screens."""

    security_id: str
    as_of_date: date
    price_date: date
    adjusted_close: float
    source: str
    average_daily_volume: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None

    def __post_init__(self) -> None:
        if self.price_date > self.as_of_date:
            raise ValueError("price_date cannot be after the as-of date")
        if self.adjusted_close <= 0:
            raise ValueError("adjusted_close must be positive")


@dataclass(frozen=True, slots=True)
class ScreeningRecord:
    """One algorithm-ready, point-in-time observation for a security."""

    security_id: str
    ticker: str
    name: str
    exchange: str
    as_of_date: date
    period_end: date
    available_at: date
    price_date: date
    fundamentals_source: str
    price_source: str
    adjusted_close: float
    security_type: str = "common_stock"
    currency: str = "USD"
    cik: str | None = None
    figi: str | None = None
    sector: str | None = None
    industry: str | None = None
    average_daily_volume: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    revenue_ttm: float | None = None
    revenue_prior_ttm: float | None = None
    gross_profit_ttm: float | None = None
    gross_profit_prior_ttm: float | None = None
    ebit_ttm: float | None = None
    net_income_ttm: float | None = None
    net_income_prior_ttm: float | None = None
    operating_cash_flow_ttm: float | None = None
    operating_cash_flow_prior_ttm: float | None = None
    free_cash_flow_ttm: float | None = None
    free_cash_flow_prior_ttm: float | None = None
    total_assets: float | None = None
    total_assets_prior: float | None = None
    current_assets: float | None = None
    current_assets_prior: float | None = None
    current_liabilities: float | None = None
    current_liabilities_prior: float | None = None
    long_term_debt: float | None = None
    long_term_debt_prior: float | None = None
    shares_outstanding: float | None = None
    shares_outstanding_prior: float | None = None
    invested_capital: float | None = None

    def __post_init__(self) -> None:
        if self.available_at > self.as_of_date:
            raise ValueError("financial data cannot be available after the as-of date")
        if self.price_date > self.as_of_date:
            raise ValueError("price_date cannot be after the as-of date")
        if self.adjusted_close <= 0:
            raise ValueError("adjusted_close must be positive")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScreeningRecord":
        parsed = dict(value)
        for key in ("as_of_date", "period_end", "available_at", "price_date"):
            raw_value = parsed.get(key)
            if isinstance(raw_value, str):
                parsed[key] = date.fromisoformat(raw_value)
        return cls(**parsed)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            result[field.name] = value.isoformat() if isinstance(value, date) else value
        return result


@dataclass(frozen=True, slots=True)
class ScreeningContext:
    as_of_date: date
    records: tuple[ScreeningRecord, ...]
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class StockScore:
    algorithm_slug: str
    algorithm_version: str
    security_id: str
    ticker: str
    eligible: bool
    score: float | None
    rank: int | None
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metrics_used: Mapping[str, float] | None = None


@dataclass(frozen=True, slots=True)
class RunManifest:
    schema_version: int
    run_id: str
    started_at: datetime
    as_of_date: date
    universe: str
    dataset_fingerprint: str
    input_snapshot: str
    data_sources: tuple[str, ...]
    algorithms: tuple[Mapping[str, str], ...]
    parameters: Mapping[str, Any]
    evaluated_count: int
    shortlisted_count: int
