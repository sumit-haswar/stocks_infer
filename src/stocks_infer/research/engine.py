"""Build independent research dimensions; never average away missing evidence."""

from datetime import date

from stocks_infer.research.features import FactUnavailable, History, build_features, build_ttm_features
from stocks_infer.research.models import Assessment, Company, CompanyResearch, ResearchBundle
from stocks_infer.research.valuation import value_scenario


def research_company(bundle: ResearchBundle, company: Company, as_of: date) -> CompanyResearch:
    history = History(bundle.facts, company.security_id, as_of)
    annual_features = build_features(history, company.currency)
    ttm_features = build_ttm_features(history, company.currency)
    features = annual_features + ttm_features
    latest_end = history.periods[-1] if history.periods else None
    latest = {f.name: f for f in annual_features if f.period_end == latest_end}
    latest_ttm_end = max((f.period_end for f in ttm_features), default=None)

    def value(name):
        feature = latest.get(name)
        return feature.value if feature else None

    warnings: list[str] = []
    positive_years = sum(f.name == "operating_income" and f.value is not None and f.value > 0 for f in annual_features)
    reasons = [company.classification_reason] if company.classified_at <= as_of else []
    if company.classified_at > as_of:
        framework = "needs_review"
        reasons.append("No business classification available at the evaluation cutoff")
    elif company.business_type != "operating" or company.cyclical:
        framework = "different_framework"
        reasons.append("Requires a specialized or through-cycle framework; company retained for research")
    elif positive_years < 3:
        framework = "needs_review"
        reasons.append("Fewer than three positive annual operating-income observations in the latest five periods; review maturity or missing history")
    else:
        framework = "applicable"
        reasons.append("Operating business with at least three profitable annual observations in the latest five periods")

    if len(history.periods) < 5:
        warnings.append(f"Only {len(history.periods)} annual periods available; target is five plus opening balances")
    warnings.extend(f"{f.name}: {warning}" for f in latest.values() for warning in f.warnings)
    warnings.append("Annual assessment only; debt maturities and industry comparisons require further review")
    if latest_ttm_end is not None:
        warnings.append(
            f"TTM evidence through {latest_ttm_end} is displayed as a separate trend layer and does not silently replace the annual assessment"
        )
    else:
        warnings.append("No complete four-quarter TTM window could be normalized at this cutoff")
    if value("net_debt") is not None:
        warnings.append("Net debt subtracts unrestricted cash and cash equivalents only; marketable investments require a separate valuation-bridge review")
    stale_fundamentals = latest_end is None or (as_of - latest_end).days > 550
    if stale_fundamentals:
        warnings.append("Annual fundamentals are missing or older than 550 days")
    if value("equity") is not None and value("equity") <= 0:
        warnings.append("Non-positive book equity: investigate buybacks, accumulated losses, and accounting context")
    if latest_end is not None:
        try:
            debt_fact = history.get("debt", latest_end)
            if debt_fact.source_concept.startswith("derived:sum("):
                warnings.append("Debt is a filing-reconciled sum of current/noncurrent carrying amounts; operating leases and undrawn facilities are excluded")
            elif debt_fact.source_concept == "reconciled:no-interest-bearing-debt":
                warnings.append("The filing explicitly supports zero outstanding interest-bearing debt; operating leases and undrawn facilities are excluded")
        except FactUnavailable:
            pass
        try:
            interest_fact = history.get("interest_expense", latest_end)
            if "interest expense and other, net" in interest_fact.source_concept.lower():
                warnings.append(
                    "Interest coverage uses the filing's combined interest-expense-and-other-net line "
                    "because a separate comparable accrual-interest line is unavailable"
                )
            latest_ttm_interest = next(
                (
                    feature for feature in ttm_features
                    if feature.period_end == latest_ttm_end and feature.name == "interest_coverage"
                ),
                None,
            )
            if (
                "gross interest expense" in interest_fact.source_concept.lower()
                and latest_ttm_interest is not None
                and latest_ttm_interest.status == "missing"
            ):
                warnings.append(
                    "TTM interest coverage is withheld because the annual fact is gross interest expense "
                    "while the interim filing reports a net interest line; incompatible definitions are not bridged"
                )
        except FactUnavailable:
            pass
        try:
            shares_fact = history.get("diluted_shares", latest_end)
            if "common stock shares outstanding - assuming dilution" in shares_fact.source_concept.lower():
                warnings.append(
                    "Diluted shares use the filing's total common-equivalent Common Stock denominator; "
                    "the separate Class B denominator is not added again"
                )
        except FactUnavailable:
            pass
    if value("revenue_growth") is not None and abs(value("revenue_growth")) > .5:
        warnings.append("Revenue changed by more than 50%; investigate acquisitions, disposals, and reporting-boundary changes before treating it as organic growth")
    if value("share_growth") is not None and abs(value("share_growth")) > .5:
        warnings.append("Weighted-average shares changed by more than 50%; investigate mergers, listings, and other capital-structure discontinuities")
    if value("operating_income") is not None and value("operating_income") > 0 and value("net_income") is not None and value("net_income") > 1.5 * value("operating_income"):
        warnings.append("Net income materially exceeds operating income; inspect tax benefits and non-operating gains before treating earnings as recurring")
    if value("pretax_return_on_capital") is not None and value("pretax_return_on_capital") > 1:
        warnings.append("Capital-return approximation exceeds 100%; inspect cash subtraction, lease obligations, and negative working capital before comparison")
    if value("debt") == 0 and latest_end is not None:
        try:
            annual_start = history.get("revenue", latest_end).period_start
            interest_fact = history.get("interest_expense", latest_end, start=annual_start)
            if interest_fact.value > 0:
                warnings.append("Year-end debt is zero but annual interest expense is positive; investigate intra-year borrowings, commitment fees, and other interest-bearing liabilities")
        except FactUnavailable:
            pass

    assessments = []

    def assess(dimension, checks):
        observations, outcomes = [], []
        unresolved = False
        for metric, predicate, favorable, unfavorable in checks:
            feature = latest.get(metric)
            if feature is not None and feature.status == "not_meaningful":
                observations.append(f"{metric}: not meaningful — {feature.explanation}")
                continue
            observed = value(metric)
            if observed is None:
                explanation = latest[metric].explanation if metric in latest else "No annual observations"
                observations.append(f"{metric}: unavailable — {explanation}")
                unresolved = True
            else:
                passed = predicate(observed)
                outcomes.append(passed)
                observations.append(f"{metric}: {favorable if passed else unfavorable}")
        if not outcomes:
            status = "insufficient_evidence"
        elif any(outcome is False for outcome in outcomes):
            status = "mixed" if any(outcomes) else "concerns"
        elif unresolved:
            status = "incomplete"
        else:
            status = "supportive"
        assessments.append(Assessment(dimension, status, tuple(observations)))

    assess("quality", [
        ("operating_margin", lambda v: v > 0, "positive operating margin", "operating losses need context"),
        ("cash_conversion", lambda v: v >= .8, "cash conversion at least 0.8x", "cash conversion below 0.8x; investigate working capital"),
        ("pretax_return_on_capital", lambda v: v >= .1, "pre-tax capital return at least 10%", "pre-tax capital return below 10%; examine reinvestment"),
    ])
    assess("growth", [
        ("revenue_growth", lambda v: v > 0, "annual revenue increased", "annual revenue did not increase; investigate mix/cycle"),
        ("share_growth", lambda v: v <= .02, "weighted-average share growth at most 2%", "share growth exceeds 2%; check splits, acquisitions, and compensation"),
    ])
    assess("resilience", [
        ("operating_cash_flow", lambda v: v > 0, "positive operating cash flow", "negative operating cash flow; review funding needs"),
        ("interest_coverage", lambda v: v >= 3, "operating income covers interest at least 3x", "interest coverage below 3x; review debt maturities"),
    ])
    if value("free_cash_flow") is not None and value("free_cash_flow") < 0:
        warnings.append("Negative free cash flow: investigate expansion versus maintenance spending and funding; no automatic exclusion")
    if value("interest_coverage") is not None and value("interest_coverage") < 1:
        warnings.append("HIGH PRIORITY: operating income does not cover interest expense")
    if framework != "applicable":
        assessments = [Assessment(a.dimension, "not_assessed", (
            "Established-business yardstick withheld pending framework review; raw annual features remain available",
        )) for a in assessments]

    prices = [p for p in bundle.prices if p.security_id == company.security_id and p.available_at <= as_of]
    market = None
    if prices:
        latest_date = max(p.price_date for p in prices)
        current = [p for p in prices if p.price_date == latest_date]
        available_at = max(p.available_at for p in current)
        current = [p for p in current if p.available_at == available_at]
        if len({(p.close, p.shares_outstanding, p.share_count_date) for p in current}) > 1:
            warnings.append("Conflicting market observations; valuation withheld until reconciled")
        else:
            market = sorted(current, key=lambda p: p.source_id)[0]
    stale_market = market is None or (as_of - market.price_date).days > 7 or (market.price_date - market.share_count_date).days > 180
    if stale_market:
        warnings.append("Price is missing/older than seven days, or outstanding share count is older than 180 days")

    theses = [t for t in bundle.theses if t.security_id == company.security_id and t.authored_at <= as_of]
    thesis = max(theses, key=lambda t: (t.authored_at, t.version)) if theses else None
    if thesis is None:
        warnings.append("No thesis available at the evaluation cutoff")
    elif thesis.next_review is not None and thesis.next_review < as_of:
        warnings.append("Thesis review is overdue")

    valuations = []
    scenarios = [s for s in bundle.scenarios if s.security_id == company.security_id and s.authored_at <= as_of and thesis is not None and s.thesis_version == thesis.version]
    if framework == "applicable" and market and value("revenue") is not None and value("net_debt") is not None:
        for name in ("bear", "base", "bull"):
            versions = [s for s in scenarios if s.name == name]
            if not versions:
                continue
            scenario = max(versions, key=lambda s: s.authored_at)
            try:
                valuation = value_scenario(scenario, revenue=value("revenue"), net_debt=value("net_debt"), shares=market.shares_outstanding, price=market.close)
                valuation["input_ids"] = sorted(set(latest["revenue"].input_ids + latest["net_debt"].input_ids))
                valuation["market_source_ids"] = sorted({market.source_id, market.effective_share_source_id})
                valuations.append(valuation)
            except ValueError as error:
                warnings.append(f"{name} valuation unavailable: {error}")
    base = next((v for v in valuations if v["name"] == "base"), None)
    if framework == "applicable" and len(valuations) < 3:
        warnings.append("Bear/base/bull scenario set is incomplete; no missing scenario is inferred")
    if base is None:
        valuation_status = "insufficient_evidence"
        valuation_observations = ("Supply an applicable framework, dated thesis, base scenario, price, shares, revenue, cash and debt",)
    else:
        valuation_status = "scenario_available"
        valuation_observations = (f"Base-case value relative to price: {base['upside']:+.1%}; conditional on researcher assumptions", "Scenario values are not probabilities or an investment recommendation")
    assessments.append(Assessment("valuation", valuation_status, valuation_observations))
    unresolved = [f.name for f in latest.values() if f.status in {"missing", "invalid"}]
    not_meaningful = [f.name for f in latest.values() if f.status == "not_meaningful"]
    available_count = sum(f.status == "available" for f in latest.values())
    coverage_complete = bool(latest) and not unresolved and len(history.periods) >= 5 and not stale_fundamentals
    assessments.append(Assessment("evidence", "available_for_annual_review" if coverage_complete else "incomplete", (
        f"{len(history.periods)} annual periods; {available_count}/{len(latest)} latest features have values; {len(not_meaningful)} structurally not meaningful",
        "Unresolved features: " + (", ".join(unresolved) or "none"),
        "Structurally not meaningful: " + (", ".join(not_meaningful) or "none"),
        "Evidence coverage is separate from business quality; narrative completeness and quarterly evidence need manual review",
    )))

    lists = []
    if framework != "applicable":
        lists.append("framework_review")
    if not coverage_complete or base is None or stale_market:
        lists.append("evidence_needed")
    quality = assessments[0].status
    severe_funding_concern = value("interest_coverage") is not None and value("interest_coverage") < 1
    has_concerns = any(a.status in {"mixed", "concerns"} for a in assessments[:3]) or (value("free_cash_flow") is not None and value("free_cash_flow") < 0)
    if has_concerns:
        lists.append("investigate_weaknesses")
    # These are research queues, not acceptance gates. Unsupported/missing
    # valuations remain in other queues rather than receiving a zero score.
    if base and not stale_market and not stale_fundamentals:
        if base["upside"] >= .15:
            lists.append("quality_at_potentially_attractive_price" if quality == "supportive" and not severe_funding_concern else "valuation_opportunity_needing_review")
        elif quality == "supportive" and not severe_funding_concern:
            lists.append("quality_price_watch")
    if not lists:
        lists.append("general_research")
    return CompanyResearch(company.security_id, company.ticker, company.name, company.currency, framework, tuple(reasons), len(history.periods), features, tuple(assessments), tuple(lists), tuple(warnings), thesis, tuple(valuations), market)


def research_watchlist(bundle: ResearchBundle, as_of: date) -> tuple[CompanyResearch, ...]:
    return tuple(research_company(bundle, c, as_of) for c in sorted(bundle.companies, key=lambda c: (c.ticker, c.security_id)))
