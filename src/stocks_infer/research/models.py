"""Validated input contracts for the first recorded-data research workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any


FLOW_METRICS = frozenset({
    "revenue", "operating_income", "net_income", "operating_cash_flow",
    "capital_expenditure", "interest_expense", "diluted_shares",
})
BALANCE_METRICS = frozenset({"cash", "debt", "equity", "assets"})


def finite(value: float, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    title: str
    url: str
    published_at: date
    retrieved_at: date
    accession: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id or not self.title or not self.url:
            raise ValueError("source ID, title, and URL are required")
        if self.retrieved_at < self.published_at:
            raise ValueError("source retrieval cannot precede publication")


@dataclass(frozen=True)
class FinancialFact:
    fact_id: str
    security_id: str
    metric: str
    value: float
    unit: str
    period_end: date
    available_at: date
    source_id: str
    source_concept: str
    period_type: str
    period_start: date | None = None

    def __post_init__(self) -> None:
        finite(self.value, self.metric)
        if not all((self.fact_id, self.security_id, self.source_id, self.source_concept)):
            raise ValueError("fact identifiers and source concept are required")
        if self.metric not in FLOW_METRICS | BALANCE_METRICS:
            raise ValueError(f"unsupported canonical metric: {self.metric}")
        if self.available_at < self.period_end:
            raise ValueError("fact availability cannot precede period end")
        if self.metric in BALANCE_METRICS:
            if self.period_type != "instant" or self.period_start is not None:
                raise ValueError("balance-sheet facts must be instantaneous")
        else:
            if self.period_type not in {"annual", "quarter", "ytd"} or self.period_start is None:
                raise ValueError("flow facts need a start date and annual/quarter/ytd type")
            days = (self.period_end - self.period_start).days + 1
            limits = {"annual": (330, 400), "quarter": (60, 110), "ytd": (60, 400)}
            low, high = limits[self.period_type]
            if not low <= days <= high:
                raise ValueError(f"invalid {self.period_type} period length for {self.fact_id}")
        if self.metric == "diluted_shares" and (self.unit != "shares" or self.value <= 0):
            raise ValueError("diluted_shares must be positive and expressed in shares")
        if self.metric in {"capital_expenditure", "interest_expense"} and self.value < 0:
            raise ValueError(f"{self.metric} must use a positive expense/outflow convention")


@dataclass(frozen=True)
class MarketObservation:
    security_id: str
    price_date: date
    available_at: date
    close: float
    shares_outstanding: float
    currency: str
    source_id: str
    share_count_date: date
    adjustment: str = "unadjusted"

    def __post_init__(self) -> None:
        finite(self.close, "close")
        finite(self.shares_outstanding, "shares_outstanding")
        if self.close <= 0 or self.shares_outstanding <= 0:
            raise ValueError("price and outstanding shares must be positive")
        if self.price_date > self.available_at or self.share_count_date > self.price_date:
            raise ValueError("invalid market observation dates")
        if self.adjustment != "unadjusted":
            raise ValueError("valuation requires an unadjusted price and matching share basis")


@dataclass(frozen=True)
class Company:
    security_id: str
    ticker: str
    name: str
    currency: str
    business_type: str
    classification_reason: str
    classified_at: date
    cyclical: bool = False

    def __post_init__(self) -> None:
        if not all((self.security_id, self.ticker, self.name, self.currency, self.classification_reason)):
            raise ValueError("company identity and classification reason are required")
        if self.business_type not in {"operating", "bank", "insurance", "reit", "pre_revenue", "other"}:
            raise ValueError("unsupported business_type")
        if not isinstance(self.cyclical, bool):
            raise ValueError("cyclical must be a boolean")


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    assumption: bool
    source_ids: tuple[str, ...]
    counterargument: str
    metric: str
    expected_outcome: str
    review_on: date
    invalidated_by: str


@dataclass(frozen=True)
class Thesis:
    security_id: str
    version: str
    authored_at: date
    business_description: str
    opportunity: str
    claims: tuple[Claim, ...]
    decision: str = "research"
    next_review: date | None = None


@dataclass(frozen=True)
class Scenario:
    security_id: str
    name: str
    authored_at: date
    thesis_version: str
    claim_ids: tuple[str, ...]
    rationale: str
    revenue_growth: tuple[float, ...]
    operating_margins: tuple[float, ...]
    tax_rate: float
    sales_to_capital: float
    discount_rate: float
    terminal_growth: float
    terminal_roic: float

    def __post_init__(self) -> None:
        if self.name not in {"bear", "base", "bull"}:
            raise ValueError("scenario name must be bear, base, or bull")
        if len(self.revenue_growth) != 5 or len(self.operating_margins) != 5:
            raise ValueError("scenario requires five annual growth and margin assumptions")
        for name in ("tax_rate", "sales_to_capital", "discount_rate", "terminal_growth", "terminal_roic"):
            finite(getattr(self, name), name)
        for value in (*self.revenue_growth, *self.operating_margins):
            finite(value, "scenario assumption")
        if any(g <= -1 for g in self.revenue_growth):
            raise ValueError("revenue growth must exceed -100%")
        if any(not -1 <= margin <= 1 for margin in self.operating_margins):
            raise ValueError("operating margins must be between -100% and 100%")
        if not 0 <= self.tax_rate < 1 or self.sales_to_capital <= 0:
            raise ValueError("invalid tax rate or sales-to-capital ratio")
        if not 0 <= self.terminal_growth < self.discount_rate or self.terminal_roic <= self.terminal_growth:
            raise ValueError("require 0 <= terminal growth < discount rate and terminal ROIC > growth")
        if not self.rationale or not self.claim_ids or not self.thesis_version:
            raise ValueError("scenario needs a rationale and links to a thesis and its claims")


@dataclass(frozen=True)
class ResearchBundle:
    companies: tuple[Company, ...]
    sources: tuple[SourceDocument, ...]
    facts: tuple[FinancialFact, ...]
    prices: tuple[MarketObservation, ...]
    theses: tuple[Thesis, ...] = ()
    scenarios: tuple[Scenario, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or not self.companies:
            raise ValueError("nonempty schema-version-1 research bundle required")
        for values, key in ((self.companies, "security_id"), (self.sources, "source_id"), (self.facts, "fact_id")):
            ids = [getattr(item, key) for item in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {key}")
        companies = {item.security_id: item for item in self.companies}
        sources = {item.source_id: item for item in self.sources}
        for item in (*self.facts, *self.prices):
            if item.security_id not in companies or item.source_id not in sources:
                raise ValueError("unknown security or source reference")
            if sources[item.source_id].published_at > item.available_at:
                raise ValueError("value cannot be available before its source publication")
            expected = companies[item.security_id].currency
            unit = item.unit if isinstance(item, FinancialFact) else item.currency
            if unit != ("shares" if isinstance(item, FinancialFact) and item.metric == "diluted_shares" else expected):
                raise ValueError("currency/unit mismatch; convert explicitly before importing")
        thesis_keys: set[tuple[str, str]] = set()
        thesis_dates: set[tuple[str, date]] = set()
        for thesis in self.theses:
            key = (thesis.security_id, thesis.version)
            if thesis.security_id not in companies or key in thesis_keys or not thesis.version:
                raise ValueError("unknown company or duplicate/empty thesis version")
            thesis_keys.add(key)
            if (thesis.security_id, thesis.authored_at) in thesis_dates:
                raise ValueError("ambiguous thesis revisions on the same date")
            thesis_dates.add((thesis.security_id, thesis.authored_at))
            if not thesis.business_description or not thesis.opportunity:
                raise ValueError("thesis needs a business description and opportunity")
            claim_ids = [claim.claim_id for claim in thesis.claims]
            if len(set(claim_ids)) != len(claim_ids):
                raise ValueError("duplicate claim ID within thesis")
            for claim in thesis.claims:
                if not all((claim.claim_id, claim.text, claim.counterargument, claim.metric, claim.expected_outcome, claim.invalidated_by)):
                    raise ValueError("claims need text, counterevidence, milestones, and invalidation conditions")
                if not isinstance(claim.assumption, bool) or (not claim.assumption and not claim.source_ids):
                    raise ValueError("a claim needs evidence or an explicit assumption label")
                if any(s not in sources for s in claim.source_ids):
                    raise ValueError("unknown claim source")
                if any(sources[s].published_at > thesis.authored_at for s in claim.source_ids):
                    raise ValueError("thesis cannot cite a future source")
        scenario_keys: set[tuple[str, str, date]] = set()
        for scenario in self.scenarios:
            key = (scenario.security_id, scenario.name, scenario.authored_at)
            if key in scenario_keys:
                raise ValueError("duplicate scenario revision")
            scenario_keys.add(key)
            thesis = next((t for t in self.theses if (t.security_id, t.version) == (scenario.security_id, scenario.thesis_version)), None)
            if thesis is None or thesis.authored_at > scenario.authored_at:
                raise ValueError("scenario needs an existing thesis available when authored")
            if not set(scenario.claim_ids) <= {c.claim_id for c in thesis.claims}:
                raise ValueError("scenario refers to an unknown thesis claim")


@dataclass(frozen=True)
class FeatureValue:
    name: str
    period_end: date
    value: float | None
    unit: str
    status: str
    input_ids: tuple[str, ...]
    explanation: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Assessment:
    dimension: str
    status: str
    observations: tuple[str, ...]


@dataclass(frozen=True)
class CompanyResearch:
    security_id: str
    ticker: str
    name: str
    currency: str
    framework_status: str
    framework_reasons: tuple[str, ...]
    annual_periods: int
    features: tuple[FeatureValue, ...]
    assessments: tuple[Assessment, ...]
    lists: tuple[str, ...]
    warnings: tuple[str, ...]
    thesis: Thesis | None
    valuation: tuple[dict[str, Any], ...] = ()
    market: MarketObservation | None = None
    # No overall score: data sufficiency, framework applicability and business
    # evidence are separate throughout the workflow.
