"""Interfaces implemented by external data-provider adapters."""

from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence, runtime_checkable

from stocks_infer.models import FinancialSnapshot, PriceSnapshot, Security


@runtime_checkable
class UniverseProvider(Protocol):
    provider_name: str

    def fetch_universe(self, as_of_date: date) -> Sequence[Security]:
        """Return securities eligible for consideration on the requested date."""
        ...


@runtime_checkable
class FundamentalsProvider(Protocol):
    provider_name: str

    def fetch_fundamentals(
        self, securities: Sequence[Security], as_of_date: date
    ) -> Sequence[FinancialSnapshot]:
        """Return the latest fundamentals available by the requested date."""
        ...


@runtime_checkable
class MarketDataProvider(Protocol):
    provider_name: str

    def fetch_prices(
        self, securities: Sequence[Security], as_of_date: date
    ) -> Sequence[PriceSnapshot]:
        """Return end-of-day prices at or before the requested date."""
        ...
