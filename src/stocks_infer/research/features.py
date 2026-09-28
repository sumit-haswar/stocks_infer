"""Annual, point-in-time features with explicit missing/invalid denominators."""

from __future__ import annotations

from datetime import date, timedelta
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

    def get_quarter(self, metric: str, start: date, end: date) -> FinancialFact:
        candidates = [
            fact for fact in self.facts
            if fact.metric == metric and fact.period_type == "quarter"
            and fact.period_start == start and fact.period_end == end
        ]
        return self._select(candidates, f"{metric} for quarter {start} to {end}")

    def get_instant(self, metric: str, end: date) -> FinancialFact:
        candidates = [
            fact for fact in self.facts
            if fact.metric == metric and fact.period_type == "instant" and fact.period_end == end
        ]
        return self._select(candidates, f"{metric} at {end}")

    def ttm_bridge(self, metric: str, start: date, end: date) -> tuple[float, tuple[FinancialFact, ...]]:
        """Return annual + current YTD - prior comparable YTD."""
        current_candidates = [
            fact for fact in self.facts
            if fact.metric == metric and fact.period_type == "ytd" and fact.period_end == end
        ]
        current = self._select(current_candidates, f"current YTD {metric} ending {end}")
        current_days = (current.period_end - current.period_start).days + 1
        prior_candidates = [
            fact for fact in self.facts
            if fact.metric == metric and fact.period_type == "ytd"
            and 330 <= (current.period_end - fact.period_end).days <= 400
            and abs(((fact.period_end - fact.period_start).days + 1) - current_days) <= 7
        ]
        if not prior_candidates:
            raise FactUnavailable(f"Missing prior comparable YTD {metric}")
        prior_end = max(fact.period_end for fact in prior_candidates)
        prior = self._select(
            [fact for fact in prior_candidates if fact.period_end == prior_end],
            f"prior comparable YTD {metric} ending {prior_end}",
        )
        annual_candidates = [
            fact for fact in self.facts
            if fact.metric == metric and fact.period_type == "annual"
            and fact.period_start == prior.period_start
            and prior.period_end < fact.period_end < current.period_end
        ]
        annual = self._select(annual_candidates, f"annual bridge {metric} after {prior.period_end}")
        ttm_days = (end - start).days + 1
        if metric == "diluted_shares":
            annual_days = (annual.period_end - annual.period_start).days + 1
            prior_days = (prior.period_end - prior.period_start).days + 1
            value = (annual.value * annual_days + current.value * current_days - prior.value * prior_days) / ttm_days
        else:
            value = annual.value + current.value - prior.value
        return value, (annual, current, prior)

    def quarter_windows(self) -> tuple[tuple[FinancialFact, ...], ...]:
        """Return contiguous four-quarter windows anchored to a reported flow."""
        anchors: list[FinancialFact] = []
        for metric in ("revenue", "operating_income", "net_income", "operating_cash_flow"):
            intervals = sorted({
                (fact.period_start, fact.period_end)
                for fact in self.facts
                if fact.metric == metric and fact.period_type == "quarter"
            }, key=lambda interval: interval[1])
            for start, end in intervals:
                try:
                    anchors.append(self.get_quarter(metric, start, end))
                except FactUnavailable:
                    continue
            if anchors:
                break
        windows = []
        for index in range(3, len(anchors)):
            window = tuple(anchors[index - 3:index + 1])
            contiguous = all(
                later.period_start == earlier.period_end + timedelta(days=1)
                for earlier, later in zip(window, window[1:])
            )
            days = (window[-1].period_end - window[0].period_start).days + 1
            if contiguous and 330 <= days <= 400:
                windows.append(window)
        return tuple(windows)

    @staticmethod
    def _select(candidates: list[FinancialFact], label: str) -> FinancialFact:
        if not candidates:
            raise FactUnavailable(f"Missing {label}")
        latest_date = max(fact.available_at for fact in candidates)
        latest = [fact for fact in candidates if fact.available_at == latest_date]
        if len({(fact.value, fact.period_start, fact.unit) for fact in latest}) > 1:
            raise FactUnavailable(f"Conflicting {label} facts at {latest_date}; reconcile sources", "invalid")
        return sorted(latest, key=lambda fact: fact.fact_id)[0]


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
            # Use revenue's interval when available. Specialty businesses may
            # lack a comparable total-revenue concept; their reported annual
            # flows still remain visible, anchored to another annual flow.
            anchor = None
            for anchor_metric in ("revenue", "operating_income", "net_income", "operating_cash_flow"):
                try:
                    anchor = history.get(anchor_metric, target)
                    break
                except FactUnavailable as error:
                    if error.status == "invalid":
                        raise
            if anchor is None:
                raise FactUnavailable(f"No annual flow interval for {target}")
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
            equity, prior_equity = read("equity"), read("equity", True)
            if equity <= 0 or prior_equity <= 0:
                raise FactUnavailable("Non-positive book equity can distort this capital-return approximation; review capital allocation and financing", "not_meaningful")
            current = read("debt") + equity - read("cash")
            prior = read("debt", True) + prior_equity - read("cash", True)
            if current <= 0 or prior <= 0:
                raise FactUnavailable("Non-positive invested capital; examine buybacks and accounting before interpreting returns", "not_meaningful")
            return read("operating_income") / ((current + prior) / 2)

        def interest_coverage() -> float:
            try:
                expense = read("interest_expense")
            except FactUnavailable as error:
                if error.status == "missing" and read("debt") == 0:
                    raise FactUnavailable(
                        "Explicit zero year-end debt and no reported interest expense; coverage is structurally not meaningful",
                        "not_meaningful",
                    ) from error
                raise
            return positive_ratio(read("operating_income"), expense)

        def add(name: str, unit: str, formula: str, calculate: Callable[[], float]) -> None:
            used.clear()
            status, value, explanation = "available", None, formula
            feature_warnings: list[str] = []
            try:
                value = calculate()
                if not math.isfinite(value):
                    raise FactUnavailable("Calculation produced a non-finite result", "invalid")
                if name in {"revenue_growth", "share_growth"} and previous is not None:
                    period_metric = "revenue" if name == "revenue_growth" else "diluted_shares"
                    current_period = history.get(period_metric, end)
                    prior_period = history.get(period_metric, previous)
                    current_days = (current_period.period_end - current_period.period_start).days + 1
                    prior_days = (prior_period.period_end - prior_period.period_start).days + 1
                    if abs(current_days - prior_days) >= 5:
                        feature_warnings.append(
                            f"Fiscal-year lengths differ ({current_days} versus {prior_days} days); growth is not week-adjusted"
                        )
            except FactUnavailable as error:
                value = None
                status, explanation = error.status, f"{formula}. {error}"
            results.append(FeatureValue(name, end, value, unit, status, tuple(sorted({f.fact_id for f in used})), explanation, tuple(feature_warnings)))

        for metric in ("revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure", "cash", "debt", "equity"):
            add(metric, currency, f"Reported {metric}", lambda m=metric: read(m))
        add("operating_margin", "ratio", "Operating income / revenue", lambda: positive_ratio(read("operating_income"), read("revenue")))
        add("cash_conversion", "multiple", "Operating cash flow / positive net income", lambda: positive_ratio(read("operating_cash_flow"), read("net_income")))
        add("free_cash_flow", currency, "Operating cash flow - capital expenditure (equity cash-flow proxy, not FCFF)", lambda: read("operating_cash_flow") - read("capital_expenditure"))
        add("revenue_growth", "ratio", "Current annual revenue / previous annual revenue - 1", lambda: change("revenue"))
        add("share_growth", "ratio", "Current / previous diluted weighted-average shares - 1; changes require split/acquisition context", lambda: change("diluted_shares"))
        add("interest_coverage", "multiple", "Operating income / positive interest expense", interest_coverage)
        add("net_debt", currency, "Debt - cash", lambda: read("debt") - read("cash"))
        add("pretax_return_on_capital", "ratio", "Operating income / average(debt + equity - cash); pre-tax approximation, not after-tax ROIC", capital_return)
    return tuple(results)


def build_ttm_features(history: History, currency: str) -> tuple[FeatureValue, ...]:
    """Build rolling TTM features from four contiguous normalized quarters."""
    windows = history.quarter_windows()
    results: list[FeatureValue] = []
    for index, window in enumerate(windows):
        if index < len(windows) - 5:
            continue
        end = window[-1].period_end
        prior_window = windows[index - 4] if index >= 4 else None
        used: list[FinancialFact] = []

        def flow(metric: str, selected=window) -> float:
            try:
                facts = [history.get_quarter(metric, anchor.period_start, anchor.period_end) for anchor in selected]
                used.extend(facts)
                if metric == "diluted_shares":
                    days = [(fact.period_end - fact.period_start).days + 1 for fact in facts]
                    return sum(fact.value * span for fact, span in zip(facts, days)) / sum(days)
                return sum(fact.value for fact in facts)
            except FactUnavailable as error:
                if error.status != "missing":
                    raise
                value, facts = history.ttm_bridge(metric, selected[0].period_start, selected[-1].period_end)
                used.extend(facts)
                return value

        def balance(metric: str, *, opening: bool = False) -> float:
            target = window[0].period_start - timedelta(days=1) if opening else end
            fact = history.get_instant(metric, target)
            used.append(fact)
            return fact.value

        def positive_ratio(numerator: float, denominator: float) -> float:
            if denominator <= 0:
                raise FactUnavailable("Non-positive denominator; ratio is not meaningful", "not_meaningful")
            return numerator / denominator

        def growth(metric: str) -> float:
            if prior_window is None:
                raise FactUnavailable("Missing comparable prior TTM window")
            current = flow(metric)
            prior = flow(metric, prior_window)
            return positive_ratio(current, prior) - 1

        def interest_coverage() -> float:
            try:
                expense = flow("interest_expense")
            except FactUnavailable as error:
                if error.status == "missing" and balance("debt") == 0:
                    raise FactUnavailable(
                        "Explicit zero period-end debt and no reported TTM interest expense; coverage is structurally not meaningful",
                        "not_meaningful",
                    ) from error
                raise
            return positive_ratio(flow("operating_income"), expense)

        def capital_return() -> float:
            closing_equity, opening_equity = balance("equity"), balance("equity", opening=True)
            if closing_equity <= 0 or opening_equity <= 0:
                raise FactUnavailable(
                    "Non-positive book equity can distort this TTM capital-return approximation",
                    "not_meaningful",
                )
            closing = balance("debt") + closing_equity - balance("cash")
            opening = balance("debt", opening=True) + opening_equity - balance("cash", opening=True)
            if closing <= 0 or opening <= 0:
                raise FactUnavailable("Non-positive invested capital; TTM return is not meaningful", "not_meaningful")
            return flow("operating_income") / ((closing + opening) / 2)

        def add(name: str, unit: str, formula: str, calculate: Callable[[], float]) -> None:
            used.clear()
            status, value, explanation = "available", None, formula
            feature_warnings: list[str] = []
            try:
                value = calculate()
                if not math.isfinite(value):
                    raise FactUnavailable("Calculation produced a non-finite result", "invalid")
                if name in {"revenue_growth", "share_growth"} and prior_window is not None:
                    current_days = (window[-1].period_end - window[0].period_start).days + 1
                    prior_days = (prior_window[-1].period_end - prior_window[0].period_start).days + 1
                    if abs(current_days - prior_days) >= 5:
                        feature_warnings.append(
                            f"TTM lengths differ ({current_days} versus {prior_days} days); growth is not week-adjusted"
                        )
            except FactUnavailable as error:
                status, explanation = error.status, f"{formula}. {error}"
            results.append(FeatureValue(
                name, end, value, unit, status,
                tuple(sorted({fact.fact_id for fact in used})), explanation,
                tuple(feature_warnings), "ttm",
            ))

        for metric in ("revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure"):
            add(
                metric,
                currency,
                f"TTM {metric}: four contiguous normalized quarters; annual + current YTD - prior comparable YTD when a discrete metric quarter is absent",
                lambda m=metric: flow(m),
            )
        for metric in ("cash", "debt", "equity"):
            add(metric, currency, f"Reported {metric} at TTM period end", lambda m=metric: balance(m))
        add("operating_margin", "ratio", "TTM operating income / TTM revenue", lambda: positive_ratio(flow("operating_income"), flow("revenue")))
        add("cash_conversion", "multiple", "TTM operating cash flow / positive TTM net income", lambda: positive_ratio(flow("operating_cash_flow"), flow("net_income")))
        add("free_cash_flow", currency, "TTM operating cash flow - TTM capital expenditure", lambda: flow("operating_cash_flow") - flow("capital_expenditure"))
        add("revenue_growth", "ratio", "Current TTM revenue / prior-year TTM revenue - 1", lambda: growth("revenue"))
        add("share_growth", "ratio", "Current / prior-year TTM weighted diluted shares - 1", lambda: growth("diluted_shares"))
        add("interest_coverage", "multiple", "TTM operating income / positive TTM interest expense", interest_coverage)
        add("net_debt", currency, "Period-end debt - period-end cash", lambda: balance("debt") - balance("cash"))
        add("pretax_return_on_capital", "ratio", "TTM operating income / average opening and closing invested capital", capital_return)
    return tuple(results)
