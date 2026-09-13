"""Assembly and validation of point-in-time screening datasets."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from typing import Sequence, TypeVar

from stocks_infer.models import (
    FinancialSnapshot,
    PriceSnapshot,
    ScreeningRecord,
    Security,
)


def build_screening_records(
    securities: Sequence[Security],
    fundamentals: Sequence[FinancialSnapshot],
    prices: Sequence[PriceSnapshot],
    as_of_date: date,
) -> tuple[ScreeningRecord, ...]:
    """Join provider outputs by stable security ID and enforce point-in-time rules."""

    security_by_id = _index_unique(securities, "security")
    fundamentals_by_id = _index_unique(fundamentals, "fundamentals")
    prices_by_id = _index_unique(prices, "price")
    records: list[ScreeningRecord] = []

    for security_id, security in sorted(
        security_by_id.items(), key=lambda item: item[1].ticker
    ):
        financial = fundamentals_by_id.get(security_id)
        price = prices_by_id.get(security_id)
        if financial is None or price is None:
            continue
        if financial.as_of_date != as_of_date or price.as_of_date != as_of_date:
            raise ValueError(f"as-of date mismatch for {security.ticker}")

        records.append(
            ScreeningRecord(
                security_id=security.security_id,
                ticker=security.ticker,
                name=security.name,
                exchange=security.exchange,
                as_of_date=as_of_date,
                period_end=financial.period_end,
                available_at=financial.available_at,
                price_date=price.price_date,
                fundamentals_source=financial.source,
                price_source=price.source,
                adjusted_close=price.adjusted_close,
                security_type=security.security_type,
                currency=financial.currency,
                cik=security.cik,
                figi=security.figi,
                sector=security.sector,
                industry=security.industry,
                average_daily_volume=price.average_daily_volume,
                market_cap=price.market_cap,
                enterprise_value=price.enterprise_value,
                revenue_ttm=financial.revenue_ttm,
                revenue_prior_ttm=financial.revenue_prior_ttm,
                gross_profit_ttm=financial.gross_profit_ttm,
                gross_profit_prior_ttm=financial.gross_profit_prior_ttm,
                ebit_ttm=financial.ebit_ttm,
                net_income_ttm=financial.net_income_ttm,
                net_income_prior_ttm=financial.net_income_prior_ttm,
                operating_cash_flow_ttm=financial.operating_cash_flow_ttm,
                operating_cash_flow_prior_ttm=financial.operating_cash_flow_prior_ttm,
                free_cash_flow_ttm=financial.free_cash_flow_ttm,
                free_cash_flow_prior_ttm=financial.free_cash_flow_prior_ttm,
                total_assets=financial.total_assets,
                total_assets_prior=financial.total_assets_prior,
                current_assets=financial.current_assets,
                current_assets_prior=financial.current_assets_prior,
                current_liabilities=financial.current_liabilities,
                current_liabilities_prior=financial.current_liabilities_prior,
                long_term_debt=financial.long_term_debt,
                long_term_debt_prior=financial.long_term_debt_prior,
                shares_outstanding=financial.shares_outstanding,
                shares_outstanding_prior=financial.shares_outstanding_prior,
                invested_capital=financial.invested_capital,
            )
        )

    return tuple(records)


def fingerprint_screening_records(records: Sequence[ScreeningRecord]) -> str:
    """Return a stable SHA-256 fingerprint for a normalized input dataset."""

    canonical = [
        record.to_dict()
        for record in sorted(records, key=lambda item: item.security_id)
    ]
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


T = TypeVar("T", Security, FinancialSnapshot, PriceSnapshot)


def _index_unique(values: Sequence[T], label: str) -> dict[str, T]:
    indexed: dict[str, T] = {}
    for value in values:
        if value.security_id in indexed:
            raise ValueError(
                f"duplicate {label} record for security_id={value.security_id}"
            )
        indexed[value.security_id] = value
    return indexed
