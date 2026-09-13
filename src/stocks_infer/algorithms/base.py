"""Screening algorithm contract and shared ranking helpers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from stocks_infer.models import ScreeningContext, StockScore


@runtime_checkable
class ScreeningAlgorithm(Protocol):
    slug: str
    version: str
    description: str

    def required_metrics(self) -> frozenset[str]:
        """Return canonical metric names required to evaluate a security."""
        ...

    def run(self, context: ScreeningContext) -> tuple[StockScore, ...]:
        """Score every record, including explicit ineligible results."""
        ...


def competition_ranks(
    values: dict[str, float], *, higher_is_better: bool
) -> dict[str, int]:
    """Assign deterministic competition ranks while preserving equal-value ties."""

    ordered = sorted(
        values.items(),
        key=lambda item: (item[1], item[0]),
        reverse=higher_is_better,
    )
    ranks: dict[str, int] = {}
    previous_value: float | None = None
    previous_rank = 0
    for position, (key, value) in enumerate(ordered, start=1):
        rank = previous_rank if previous_value is not None and value == previous_value else position
        ranks[key] = rank
        previous_value = value
        previous_rank = rank
    return ranks


def percentile_score(rank: int, count: int) -> float:
    """Convert a best-is-one rank into a comparable zero-to-one-hundred score."""

    if count <= 1:
        return 100.0
    return round(100.0 * (count - rank) / (count - 1), 6)
