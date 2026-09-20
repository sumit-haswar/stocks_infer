"""Annual, point-in-time features with explicit missing/invalid denominators."""

from __future__ import annotations

from datetime import date
import math
from typing import Callable

from stocks_infer.research.models import BALANCE_METRICS, FeatureValue, FinancialFact


class FactUnavailable(ValueError):
    def __init__(self, message: str, status: str = "missing"):
        super().__init__(message)
        self.status = status


class History:
    def __init__(self, facts: tuple[FinancialFact, ...], security_id: str, as_of: date):
        self.facts = tuple(f for f in facts if f.security_id == security_id and f.available_at <= as_of)
        self.periods = tuple(sorted({f.period_end for f in self.facts if f.period_type == "annual"}))

    def get(self, metric: str, end: date, *, start: date | None = None) -> FinancialFact:
        candidates = [f for f in self.facts if f.metric == metric and f.period_end == end and f.period_type in {"annual", "instant"}]
        if not candidates:
            raise FactUnavailable(f"Missing {metric} for {end}")
        latest_date = max(f.available_at for f in candidates)
        latest = [f for f in candidates if f.available_at == latest_date]
        if len({(f.value, f.period_start, f.unit) for f in latest}) > 1:
            raise FactUnavailable(f"Conflicting {metric} facts for {end} at {latest_date}; reconcile sources", "invalid")
        fact = sorted(latest, key=lambda f: f.fact_id)[0]
        if start is not None and fact.period_type == "annual" and fact.period_start != start:
            raise FactUnavailable(f"Mismatched annual interval for {metric} at {end}", "invalid")
        return fact


def build_features(history: History, currency: str) -> tuple[FeatureValue, ...]:
    results: list[FeatureValue] = []
    for index, end in enumerate(history.periods):
        if index < len(history.periods) - 5:
            continue
        previous = history.periods[index - 1] if index else None
        if previous and not 330 <= (end - previous).days <= 400:
            previous = None
        used: list[FinancialFact] = []

        def read(metric: str, prior: bool = False) -> float:
            target = previous if prior else end
            if target is None:
                raise FactUnavailable("Missing comparable prior annual period")
            if metric in BALANCE_METRICS:
                fact = history.get(metric, target)
                used.append(fact)
                return fact.value
            # Anchor all duration measures to the revenue interval. This catches
            # mixed fiscal calendars instead of treating them as comparable.
            anchor = history.get("revenue", target)
            fact = history.get(metric, target, start=anchor.period_start)
            used.extend((anchor, fact))
            return fact.value

        def positive_ratio(numerator: float, denominator: float) -> float:
            if denominator <= 0:
                raise FactUnavailable("Non-positive denominator; ratio is not meaningful", "not_meaningful")
            return numerator / denominator

        def change(metric: str) -> float:
            current, prior = read(metric), read(metric, True)
            return positive_ratio(current, prior) - 1

        def capital_return() -> float:
            current = read("debt") + read("equity") - read("cash")
            prior = read("debt", True) + read("equity", True) - read("cash", True)
            if current <= 0 or prior <= 0:
                raise FactUnavailable("Non-positive invested capital; examine buybacks and accounting before interpreting returns", "not_meaningful")
            return read("operating_income") / ((current + prior) / 2)

        def add(name: str, unit: str, formula: str, calculate: Callable[[], float]) -> None:
            used.clear()
            status, value, explanation = "available", None, formula
            try:
                value = calculate()
                if not math.isfinite(value):
                    raise FactUnavailable("Calculation produced a non-finite result", "invalid")
            except FactUnavailable as error:
                value = None
                status, explanation = error.status, f"{formula}. {error}"
            results.append(FeatureValue(name, end, value, unit, status, tuple(sorted({f.fact_id for f in used})), explanation))

        for metric in ("revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure", "cash", "debt", "equity"):
            add(metric, currency, f"Reported {metric}", lambda m=metric: read(m))
        add("operating_margin", "ratio", "Operating income / revenue", lambda: positive_ratio(read("operating_income"), read("revenue")))
        add("cash_conversion", "multiple", "Operating cash flow / positive net income", lambda: positive_ratio(read("operating_cash_flow"), read("net_income")))
        add("free_cash_flow", currency, "Operating cash flow - capital expenditure (equity cash-flow proxy, not FCFF)", lambda: read("operating_cash_flow") - read("capital_expenditure"))
        add("revenue_growth", "ratio", "Current annual revenue / previous annual revenue - 1", lambda: change("revenue"))
        add("share_growth", "ratio", "Current / previous diluted weighted-average shares - 1; changes require split/acquisition context", lambda: change("diluted_shares"))
        add("interest_coverage", "multiple", "Operating income / positive interest expense", lambda: positive_ratio(read("operating_income"), read("interest_expense")))
        add("net_debt", currency, "Debt - cash", lambda: read("debt") - read("cash"))
        add("pretax_return_on_capital", "ratio", "Operating income / average(debt + equity - cash); pre-tax approximation, not after-tax ROIC", capital_return)
    return tuple(results)
