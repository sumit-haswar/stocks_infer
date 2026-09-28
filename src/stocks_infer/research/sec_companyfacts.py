"""Reviewed annual and quarterly mappings from SEC Company Facts."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

from stocks_infer.research.models import Company, FinancialFact, ResearchBundle, SourceDocument
from stocks_infer.research.universe import UniverseCompany


# One tag per metric and company. Expand only after reconciling against filings;
# absent concepts stay absent rather than being replaced by a guessed fallback.
PILOT_CONCEPTS: dict[str, dict[str, str]] = {
    "WSM": {
        "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "operating_income": "OperatingIncomeLoss",
        "net_income": "NetIncomeLoss",
        "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
        "capital_expenditure": "PaymentsToAcquirePropertyPlantAndEquipment",
        "diluted_shares": "WeightedAverageNumberOfDilutedSharesOutstanding",
        "cash": "CashAndCashEquivalentsAtCarryingValue",
        "equity": "StockholdersEquity",
        "assets": "Assets",
    },
    "AZO": {
        "revenue": "Revenues",
        "operating_income": "OperatingIncomeLoss",
        "net_income": "NetIncomeLoss",
        "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
        "capital_expenditure": "PaymentsToAcquirePropertyPlantAndEquipment",
        "interest_expense": "InterestExpenseNonoperating",
        "diluted_shares": "WeightedAverageNumberOfDilutedSharesOutstanding",
        "cash": "CashAndCashEquivalentsAtCarryingValue",
        "debt": "DebtLongtermAndShorttermCombinedAmount",
        "equity": "StockholdersEquity",
        "assets": "Assets",
    },
}
BALANCES = frozenset({"cash", "debt", "equity", "assets"})

# Total revenue, not a similarly named component (notably ANDE, CMS, COF,
# M, and PECO). A missing total is left missing. These are provisional
# development-cohort selections; filing reconciliation is still required.
DEVELOPMENT_REVENUE = {
    "CMS": "Revenues", "QCOM": "Revenues", "COF": "Revenues",
    "WSM": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "INTU": "Revenues", "VTR": "Revenues",
    "AMGN": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "CAT": "Revenues", "AMAT": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "COHR": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "BWA": "Revenues", "FHN": "Revenues", "M": "Revenues",
    "OC": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "ESAB": "Revenues", "DUOL": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "EPR": "Revenues", "UTHR": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "COKE": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "CW": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "ANDE": "Revenues", "AMTM": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "TPC": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "PECO": "Revenues", "NEO": "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SEI": "Revenues", "ROAD": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "MD": "RevenueFromContractWithCustomerIncludingAssessedTax",
}
COMMON_CONCEPTS = {
    "operating_income": "OperatingIncomeLoss",
    "net_income": "NetIncomeLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "capital_expenditure": "PaymentsToAcquirePropertyPlantAndEquipment",
    "diluted_shares": "WeightedAverageNumberOfDilutedSharesOutstanding",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
    "equity": "StockholdersEquity",
    "assets": "Assets",
}
DEVELOPMENT_BUSINESS_TYPES = {
    "COF": "bank", "FHN": "bank",
    "VTR": "reit", "EPR": "reit", "ABR": "reit", "PECO": "reit",
    "CMS": "other", "NAVI": "other",
}
# Cyclical businesses need a through-cycle comparison before judgments.
DEVELOPMENT_CYCLICAL = frozenset({"CAT", "COHR", "BWA", "M", "OC", "ANDE", "SEI", "TPC", "ROAD"})

# Filing-reconciled carrying-debt bridges for companies routed through the
# established operating-business review. Components are summed only when they
# share the same filing accession and balance-sheet date. Operating leases and
# undrawn credit facilities are excluded.
DEVELOPMENT_DEBT_COMPONENTS = {
    "AMAT": ("LongTermDebtNoncurrent", "ShortTermBorrowings"),
    "AMGN": ("LongTermDebt",),
    "AMTM": ("LongTermDebt",),
    "COKE": ("LongTermDebt",),
    "CW": ("LongTermDebt",),
    "ESAB": ("LongTermDebtCurrent", "LongTermDebtNoncurrent"),
    "INTU": ("LongTermDebt",),
    "MD": ("LongTermDebtAndCapitalLeaseObligationsCurrent", "LongTermDebtAndCapitalLeaseObligations"),
    "QCOM": ("DebtCurrent", "LongTermDebt"),
}
PREFERRED_DEBT_TOTAL = {
    "QCOM": "DebtLongtermAndShorttermCombinedAmount",
}
# The cited filings explicitly report no outstanding interest-bearing debt at
# these and later year ends. Creating a sourced zero is different from treating
# an absent SEC tag as zero.
RECONCILED_ZERO_DEBT_START = {
    "UTHR": date(2024, 12, 31),
    "WSM": date(2025, 2, 2),
}
DEVELOPMENT_CONCEPT_OVERRIDES = {
    "CW": {"cash": "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"},
    "MD": {"capital_expenditure": "PaymentsToAcquireOtherPropertyPlantAndEquipment"},
    "QCOM": {"equity": "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"},
}

# Company Facts omits issuer-extension concepts. These observations were
# reconciled directly to the named lines in the filed 10-Ks. Each entry is
# accepted only when its exact accession and annual interval are also present
# in the saved Company Facts payload, preserving point-in-time provenance.
REVIEWED_FILING_FACTS = {
    "AMTM": (
        ("interest_expense", "2022-10-01", "2023-09-29", 397_000_000, "USD", "2025-11-25", "0001628280-25-053993", "Interest expense and other, net"),
        ("interest_expense", "2023-09-30", "2024-09-27", 438_000_000, "USD", "2025-11-25", "0001628280-25-053993", "Interest expense and other, net"),
        ("interest_expense", "2024-09-28", "2025-10-03", 353_000_000, "USD", "2025-11-25", "0001628280-25-053993", "Interest expense and other, net"),
    ),
    "COKE": (
        ("interest_expense", "2024-01-01", "2024-12-31", 62_000_000, "USD", "2026-02-18", "0001628280-26-009057", "Gross interest expense disclosed in Interest Expense, Net note"),
        ("interest_expense", "2025-01-01", "2025-12-31", 102_900_000, "USD", "2026-02-18", "0001628280-26-009057", "Gross interest expense disclosed in Interest Expense, Net note"),
        ("diluted_shares", "2023-01-01", "2023-12-31", 93_923_000, "shares", "2026-02-18", "0001628280-26-009057", "Weighted average Common Stock shares outstanding - assuming dilution"),
        ("diluted_shares", "2024-01-01", "2024-12-31", 90_524_000, "shares", "2026-02-18", "0001628280-26-009057", "Weighted average Common Stock shares outstanding - assuming dilution"),
        ("diluted_shares", "2025-01-01", "2025-12-31", 83_807_000, "shares", "2026-02-18", "0001628280-26-009057", "Weighted average Common Stock shares outstanding - assuming dilution"),
    ),
    "ESAB": (
        ("interest_expense", "2023-01-01", "2023-12-31", 85_074_000, "USD", "2026-02-20", "0001877322-26-000007", "Interest expense and other, net"),
        ("interest_expense", "2024-01-01", "2024-12-31", 64_890_000, "USD", "2026-02-20", "0001877322-26-000007", "Interest expense and other, net"),
        ("interest_expense", "2025-01-01", "2025-12-31", 83_910_000, "USD", "2026-02-20", "0001877322-26-000007", "Interest expense and other, net"),
    ),
    "QCOM": (
        ("capital_expenditure", "2022-09-26", "2023-09-24", 1_450_000_000, "USD", "2025-11-05", "0000804328-25-000085", "Capital expenditures"),
        ("capital_expenditure", "2023-09-25", "2024-09-29", 1_041_000_000, "USD", "2025-11-05", "0000804328-25-000085", "Capital expenditures"),
        ("capital_expenditure", "2024-09-30", "2025-09-28", 1_192_000_000, "USD", "2025-11-05", "0000804328-25-000085", "Capital expenditures"),
    ),
}

# Interim filing lines that are unavailable as usable us-gaap facts. Each
# observation is admitted only when the exact interval, accession, and filing
# date are present elsewhere in the saved Company Facts payload.
REVIEWED_YTD_FACTS = {
    "AMTM": (
        ("interest_expense", "2024-09-28", "2025-06-27", 261_000_000, "USD", "2026-08-11", "0001628280-26-055727", "Interest expense and other, net"),
        ("interest_expense", "2025-10-04", "2026-07-03", 209_000_000, "USD", "2026-08-11", "0001628280-26-055727", "Interest expense and other, net"),
    ),
    "COKE": (
        ("diluted_shares", "2024-01-01", "2024-06-28", 93_543_000, "shares", "2025-07-24", "0000317540-25-000070", "Weighted average Common Stock shares outstanding - assuming dilution"),
        ("diluted_shares", "2025-01-01", "2025-06-27", 87_236_000, "shares", "2026-08-05", "0001628280-26-053370", "Weighted average Common Stock shares outstanding - assuming dilution"),
        ("diluted_shares", "2026-01-01", "2026-07-03", 66_649_000, "shares", "2026-08-05", "0001628280-26-053370", "Weighted average Common Stock shares outstanding - assuming dilution"),
    ),
    "ESAB": (
        ("interest_expense", "2025-01-01", "2025-07-04", 37_781_000, "USD", "2026-08-06", "0001877322-26-000056", "Interest expense and other, net"),
        ("interest_expense", "2026-01-01", "2026-07-03", 56_200_000, "USD", "2026-08-06", "0001877322-26-000056", "Interest expense and other, net"),
    ),
    "QCOM": (
        ("capital_expenditure", "2024-09-30", "2025-06-29", 785_000_000, "USD", "2026-07-29", "0000804328-26-000086", "Capital expenditures"),
        ("capital_expenditure", "2025-09-29", "2026-06-28", 1_578_000_000, "USD", "2026-07-29", "0000804328-26-000086", "Capital expenditures"),
    ),
}

# These zero balances are stated in the cited 10-Qs. Comparative balance-sheet
# dates are anchored to the same filing instead of inferred from a missing tag.
REVIEWED_QUARTERLY_ZERO_DEBT = {
    "UTHR": (
        ("2025-06-30", "2026-08-05", "0001082554-26-000027"),
        ("2026-06-30", "2026-08-05", "0001082554-26-000027"),
    ),
    "WSM": (
        ("2025-08-03", "2026-08-28", "0000719955-26-000208"),
        ("2026-08-02", "2026-08-28", "0000719955-26-000208"),
    ),
}


def _concepts_for(ticker: str, taxonomy: dict) -> dict[str, str]:
    if ticker in PILOT_CONCEPTS:
        return PILOT_CONCEPTS[ticker]
    if ticker not in DEVELOPMENT_BUSINESS_TYPES and ticker not in DEVELOPMENT_REVENUE and ticker not in {"ABR", "NAVI"}:
        raise ValueError(f"no reviewed SEC concept map for {ticker}")
    selected = {metric: tag for metric, tag in COMMON_CONCEPTS.items() if tag in taxonomy}
    selected.update({
        metric: tag for metric, tag in DEVELOPMENT_CONCEPT_OVERRIDES.get(ticker, {}).items()
        if tag in taxonomy
    })
    if ticker in DEVELOPMENT_REVENUE:
        selected["revenue"] = DEVELOPMENT_REVENUE[ticker]
    # Only the combined debt tag represents the total required by net debt.
    if ticker not in DEVELOPMENT_DEBT_COMPONENTS and "DebtLongtermAndShorttermCombinedAmount" in taxonomy:
        selected["debt"] = "DebtLongtermAndShorttermCombinedAmount"
    for tag in ("InterestExpenseNonoperating", "InterestExpense", "InterestExpenseDebt"):
        if tag in taxonomy:
            selected["interest_expense"] = tag
            break
    return selected


def companyfacts_bundle(
    companies: tuple[UniverseCompany, ...],
    cik_by_ticker: dict[str, int],
    payloads: dict[str, dict],
    *,
    as_of: date,
    retrieved_on: date,
    annual_periods: int = 6,
    quarterly_periods: int = 12,
) -> ResearchBundle:
    """Build a no-price, no-thesis bundle from SEC Company Facts.

    Annual, reported YTD, and discrete-quarter observations remain distinct.
    Missing fields are explicit; valuation is a separate implementation step.
    """
    if annual_periods < 2 or quarterly_periods < 4 or retrieved_on < as_of:
        raise ValueError("need annual and quarterly history plus a retrieval date on/after the cutoff")
    by_ticker = {item.ticker: item for item in companies}
    output_companies: list[Company] = []
    sources: dict[str, SourceDocument] = {}
    facts: list[FinancialFact] = []
    fact_ids: set[str] = set()
    for ticker, payload in sorted(payloads.items()):
        company = by_ticker.get(ticker)
        if company is None or company.test_set == "Evaluation":
            raise ValueError(f"ticker absent or held out from development: {ticker}")
        cik = cik_by_ticker[ticker]
        if int(payload.get("cik", -1)) != cik:
            raise ValueError(f"SEC CIK mismatch for {ticker}")
        sid = f"cik:{cik:010d}"
        taxonomy = payload.get("facts", {}).get("us-gaap", {})
        concepts = _concepts_for(ticker, taxonomy)
        business_type = DEVELOPMENT_BUSINESS_TYPES.get(ticker, "operating")
        output_companies.append(Company(
            security_id=sid, ticker=ticker, name=company.name, currency="USD",
            business_type=business_type, cyclical=ticker in DEVELOPMENT_CYCLICAL,
            classification_reason=(
                f"Provisional routing from workbook Companies!C{company.workbook_row}: "
                f"{company.line_of_business}. {company.framework_consideration} "
                f"Profile: {company.profile_url}. Verify business mix and cyclicality manually."
            ),
            classified_at=as_of,
        ))
        # Periods may be evidenced by other annual flow concepts when total
        # revenue is unavailable, as with some specialty finance companies.
        annual_ends = sorted({
            date.fromisoformat(raw["end"])
            for metric, tag in concepts.items() if metric not in BALANCES
            for raw in taxonomy.get(tag, {}).get("units", {}).get("shares" if metric == "diluted_shares" else "USD", [])
            if _annual_at_cutoff(raw, as_of)
        })[-annual_periods:]
        if not annual_ends:
            raise ValueError(f"no annual 10-K facts at the cutoff for {ticker}")
        quarter_ends = sorted({
            date.fromisoformat(raw["end"])
            for metric, tag in concepts.items() if metric not in BALANCES
            for raw in taxonomy.get(tag, {}).get("units", {}).get("shares" if metric == "diluted_shares" else "USD", [])
            if _quarterly_period_type(raw, as_of) is not None
        })[-quarterly_periods:]
        for metric, tag in concepts.items():
            concept = taxonomy.get(tag)
            if concept is None:
                continue
            unit = "shares" if metric == "diluted_shares" else "USD"
            for raw in concept.get("units", {}).get(unit, []):
                if metric in BALANCES:
                    if not _instant_at_cutoff(raw, as_of) or date.fromisoformat(raw["end"]) not in set(annual_ends) | set(quarter_ends):
                        continue
                    period_type = "instant"
                elif date.fromisoformat(raw.get("end", "0001-01-01")) in annual_ends and _annual_at_cutoff(raw, as_of):
                    period_type = "annual"
                elif date.fromisoformat(raw.get("end", "0001-01-01")) in quarter_ends:
                    period_type = _quarterly_period_type(raw, as_of)
                    if period_type is None:
                        continue
                else:
                    continue
                # A few SEC InterestExpense observations carry negative signs.
                # Preserve the model's positive-expense convention by leaving
                # those observations unavailable pending filing review.
                if metric in {"capital_expenditure", "interest_expense"} and raw["val"] < 0:
                    continue
                accession = raw["accn"]
                source_id = _ensure_source(
                    sources, cik, ticker, accession, raw["filed"], retrieved_on,
                    form=raw.get("form", "10-K"),
                )
                start = date.fromisoformat(raw["start"]) if "start" in raw else None
                identity = f"{sid}/{tag}/{period_type}/{start}/{raw['end']}/{accession}/{raw['val']}"
                fact_id = "sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
                if fact_id in fact_ids:
                    continue
                fact_ids.add(fact_id)
                facts.append(FinancialFact(
                    fact_id=fact_id, security_id=sid, metric=metric,
                    value=raw["val"], unit=unit, period_start=start,
                    period_end=date.fromisoformat(raw["end"]),
                    period_type=period_type,
                    available_at=date.fromisoformat(raw["filed"]),
                    source_id=source_id, source_concept=f"us-gaap:{tag}",
                ))
        _append_reconciled_debt(
            ticker, cik, sid, taxonomy, concepts, sorted(set(annual_ends) | set(quarter_ends)), annual_ends, as_of,
            retrieved_on, sources, facts,
        )
        _append_reviewed_filing_facts(
            ticker, cik, sid, taxonomy, concepts, annual_ends, as_of,
            retrieved_on, sources, facts,
        )
        _append_reviewed_ytd_facts(
            ticker, cik, sid, taxonomy, concepts, quarter_ends, as_of,
            retrieved_on, sources, facts,
        )
        _append_reviewed_quarterly_zero_debt(
            ticker, cik, sid, taxonomy, quarter_ends, as_of,
            retrieved_on, sources, facts,
        )
        _append_derived_quarters(sid, facts)
    return ResearchBundle(
        companies=tuple(output_companies), sources=tuple(sorted(sources.values(), key=lambda s: s.source_id)),
        facts=tuple(sorted(facts, key=lambda f: (f.security_id, f.period_end, f.metric, f.available_at, f.fact_id))),
        prices=(),
    )


def _append_reconciled_debt(
    ticker: str,
    cik: int,
    security_id: str,
    taxonomy: dict,
    concepts: dict[str, str],
    balance_ends: list[date],
    annual_ends: list[date],
    as_of: date,
    retrieved_on: date,
    sources: dict[str, SourceDocument],
    facts: list[FinancialFact],
) -> None:
    components = DEVELOPMENT_DEBT_COMPONENTS.get(ticker)
    if components:
        for end in balance_ends:
            total_tag = PREFERRED_DEBT_TOTAL.get(ticker)
            total_rows = [
                raw
                for raw in taxonomy.get(total_tag, {}).get("units", {}).get("USD", [])
                if date.fromisoformat(raw.get("end", "0001-01-01")) == end
                and _instant_at_cutoff(raw, as_of)
            ] if total_tag else []
            if total_rows:
                for raw in total_rows:
                    source_id = _ensure_source(
                        sources, cik, ticker, raw["accn"], raw["filed"], retrieved_on,
                        form=raw["form"],
                    )
                    identity = f"{security_id}/{total_tag}/instant/{end}/{raw['accn']}/{raw['val']}"
                    facts.append(FinancialFact(
                        fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                        security_id=security_id, metric="debt", value=raw["val"], unit="USD",
                        period_start=None, period_end=end, period_type="instant",
                        available_at=date.fromisoformat(raw["filed"]), source_id=source_id,
                        source_concept=f"us-gaap:{total_tag}",
                    ))
                continue
            by_component: list[dict[tuple[str, str, str], set[float]]] = []
            for tag in components:
                observations: dict[tuple[str, str, str], set[float]] = {}
                for raw in taxonomy.get(tag, {}).get("units", {}).get("USD", []):
                    if date.fromisoformat(raw.get("end", "0001-01-01")) != end or not _instant_at_cutoff(raw, as_of):
                        continue
                    observations.setdefault((raw["filed"], raw["accn"], raw["form"]), set()).add(raw["val"])
                by_component.append(observations)
            common = set.intersection(*(set(values) for values in by_component)) if by_component else set()
            for filed, accession, form in sorted(common):
                values = [observations[(filed, accession, form)] for observations in by_component]
                if any(len(value) != 1 for value in values):
                    continue
                value = sum(next(iter(item)) for item in values)
                source_id = _ensure_source(sources, cik, ticker, accession, filed, retrieved_on, form=form)
                expression = "+".join(f"us-gaap:{tag}" for tag in components)
                identity = f"{security_id}/debt/{end}/{accession}/{value}/{expression}"
                facts.append(FinancialFact(
                    fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                    security_id=security_id, metric="debt", value=value, unit="USD",
                    period_start=None, period_end=end, period_type="instant",
                    available_at=date.fromisoformat(filed), source_id=source_id,
                    source_concept=f"derived:sum({expression})",
                ))
        return

    zero_start = RECONCILED_ZERO_DEBT_START.get(ticker)
    if zero_start is None:
        return
    # Anchor each explicit zero to an annual 10-K fact from the same year and
    # filing so availability and provenance remain point-in-time correct.
    anchor_tags = [concepts[name] for name in ("revenue", "operating_income", "net_income") if name in concepts]
    for end in annual_ends:
        if end < zero_start:
            continue
        anchors: dict[tuple[str, str], dict] = {}
        for tag in anchor_tags:
            for raw in taxonomy.get(tag, {}).get("units", {}).get("USD", []):
                if date.fromisoformat(raw.get("end", "0001-01-01")) == end and _annual_at_cutoff(raw, as_of):
                    anchors[(raw["filed"], raw["accn"])] = raw
            if anchors:
                break
        for (filed, accession), _ in sorted(anchors.items()):
            source_id = _ensure_source(sources, cik, ticker, accession, filed, retrieved_on)
            identity = f"{security_id}/debt/{end}/{accession}/0/reconciled"
            facts.append(FinancialFact(
                fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                security_id=security_id, metric="debt", value=0, unit="USD",
                period_start=None, period_end=end, period_type="instant",
                available_at=date.fromisoformat(filed), source_id=source_id,
                source_concept="reconciled:no-interest-bearing-debt",
            ))


def _append_reviewed_filing_facts(
    ticker: str,
    cik: int,
    security_id: str,
    taxonomy: dict,
    concepts: dict[str, str],
    annual_ends: list[date],
    as_of: date,
    retrieved_on: date,
    sources: dict[str, SourceDocument],
    facts: list[FinancialFact],
) -> None:
    """Add reviewed custom-line facts only when the saved filing is present."""
    reviewed = REVIEWED_FILING_FACTS.get(ticker, ())
    if not reviewed:
        return
    anchor_tags = [concepts[name] for name in ("revenue", "operating_income", "net_income") if name in concepts]
    for metric, start_text, end_text, value, unit, filed, accession, label in reviewed:
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
        if end not in annual_ends or date.fromisoformat(filed) > as_of:
            continue
        filing_present = any(
            raw.get("start") == start_text
            and raw.get("end") == end_text
            and raw.get("filed") == filed
            and raw.get("accn") == accession
            and _annual_at_cutoff(raw, as_of)
            for tag in anchor_tags
            for raw in taxonomy.get(tag, {}).get("units", {}).get("USD", [])
        )
        if not filing_present:
            continue
        source_id = _ensure_source(sources, cik, ticker, accession, filed, retrieved_on)
        identity = f"{security_id}/{metric}/{start}/{end}/{accession}/{value}/{label}"
        facts.append(FinancialFact(
            fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
            security_id=security_id, metric=metric, value=value, unit=unit,
            period_start=start, period_end=end, period_type="annual",
            available_at=date.fromisoformat(filed), source_id=source_id,
            source_concept=f"filing-line:{label}",
        ))


def _append_reviewed_ytd_facts(
    ticker: str,
    cik: int,
    security_id: str,
    taxonomy: dict,
    concepts: dict[str, str],
    quarter_ends: list[date],
    as_of: date,
    retrieved_on: date,
    sources: dict[str, SourceDocument],
    facts: list[FinancialFact],
) -> None:
    """Add reviewed interim lines only when their exact filing is present."""
    reviewed = REVIEWED_YTD_FACTS.get(ticker, ())
    if not reviewed:
        return
    anchor_tags = [concepts[name] for name in ("revenue", "operating_income", "net_income") if name in concepts]
    for metric, start_text, end_text, value, unit, filed, accession, label in reviewed:
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
        if end not in quarter_ends or date.fromisoformat(filed) > as_of:
            continue
        filing_present = any(
            raw.get("start") == start_text
            and raw.get("end") == end_text
            and raw.get("filed") == filed
            and raw.get("accn") == accession
            and _quarterly_period_type(raw, as_of) == "ytd"
            for tag in anchor_tags
            for raw in taxonomy.get(tag, {}).get("units", {}).get("USD", [])
        )
        if not filing_present:
            continue
        source_id = _ensure_source(sources, cik, ticker, accession, filed, retrieved_on, form="10-Q")
        identity = f"{security_id}/{metric}/ytd/{start}/{end}/{accession}/{value}/{label}"
        facts.append(FinancialFact(
            fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
            security_id=security_id, metric=metric, value=value, unit=unit,
            period_start=start, period_end=end, period_type="ytd",
            available_at=date.fromisoformat(filed), source_id=source_id,
            source_concept=f"filing-line:{label}",
        ))


def _append_reviewed_quarterly_zero_debt(
    ticker: str,
    cik: int,
    security_id: str,
    taxonomy: dict,
    quarter_ends: list[date],
    as_of: date,
    retrieved_on: date,
    sources: dict[str, SourceDocument],
    facts: list[FinancialFact],
) -> None:
    """Add filing-stated zero debt at exact quarterly balance-sheet dates."""
    for end_text, filed, accession in REVIEWED_QUARTERLY_ZERO_DEBT.get(ticker, ()):
        end = date.fromisoformat(end_text)
        if end not in quarter_ends or date.fromisoformat(filed) > as_of:
            continue
        filing_present = any(
            raw.get("end") == end_text
            and raw.get("filed") == filed
            and raw.get("accn") == accession
            and raw.get("form") == "10-Q"
            for concept in taxonomy.values()
            for rows in concept.get("units", {}).values()
            for raw in rows
        )
        if not filing_present:
            continue
        source_id = _ensure_source(sources, cik, ticker, accession, filed, retrieved_on, form="10-Q")
        identity = f"{security_id}/debt/{end}/{accession}/0/reconciled"
        facts.append(FinancialFact(
            fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
            security_id=security_id, metric="debt", value=0, unit="USD",
            period_start=None, period_end=end, period_type="instant",
            available_at=date.fromisoformat(filed), source_id=source_id,
            source_concept="reconciled:no-interest-bearing-debt",
        ))


def _ensure_source(
    sources: dict[str, SourceDocument], cik: int, ticker: str,
    accession: str, filed: str, retrieved_on: date, *, form: str = "10-K",
) -> str:
    source_id = f"sec:{accession}"
    if source_id not in sources:
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{accession}-index.htm"
        sources[source_id] = SourceDocument(
            source_id=source_id, title=f"SEC Form {form} {accession} for {ticker}",
            url=url, published_at=date.fromisoformat(filed),
            retrieved_at=retrieved_on, accession=accession,
        )
    return source_id


def _append_derived_quarters(security_id: str, facts: list[FinancialFact]) -> None:
    """Derive a discrete quarter from cumulative YTD/annual facts.

    Direct quarter facts from the same filing date take precedence. Share
    averages use day weights; other flows use subtraction.
    """
    original = tuple(fact for fact in facts if fact.security_id == security_id)
    cumulative = [fact for fact in original if fact.period_type in {"ytd", "annual"}]
    direct = [fact for fact in original if fact.period_type == "quarter"]
    for current in cumulative:
        prior_candidates = [
            fact for fact in original
            if fact.metric == current.metric
            and fact.period_type in {"quarter", "ytd"}
            and fact.period_start == current.period_start
            and fact.period_end < current.period_end
            and 60 <= (current.period_end - fact.period_end).days <= 110
            and fact.available_at <= current.available_at
        ]
        if not prior_candidates:
            continue
        prior_end = max(fact.period_end for fact in prior_candidates)
        prior_candidates = [fact for fact in prior_candidates if fact.period_end == prior_end]
        prior_available = max(fact.available_at for fact in prior_candidates)
        prior_candidates = [fact for fact in prior_candidates if fact.available_at == prior_available]
        if len({(fact.value, fact.unit) for fact in prior_candidates}) != 1:
            continue
        prior = sorted(prior_candidates, key=lambda fact: fact.fact_id)[0]
        quarter_start = prior.period_end + timedelta(days=1)
        quarter_days = (current.period_end - quarter_start).days + 1
        if not 60 <= quarter_days <= 110:
            continue
        if any(
            fact.metric == current.metric
            and fact.period_start == quarter_start
            and fact.period_end == current.period_end
            and fact.available_at == current.available_at
            for fact in direct
        ):
            continue
        if current.metric == "diluted_shares":
            current_days = (current.period_end - current.period_start).days + 1
            prior_days = (prior.period_end - prior.period_start).days + 1
            value = (current.value * current_days - prior.value * prior_days) / quarter_days
        else:
            value = current.value - prior.value
        if current.metric in {"capital_expenditure", "interest_expense"} and value < 0:
            continue
        if current.metric == "diluted_shares" and value <= 0:
            continue
        expression = f"derived:discrete-quarter({current.fact_id}-{prior.fact_id})"
        identity = f"{security_id}/{current.metric}/{quarter_start}/{current.period_end}/{current.available_at}/{value}/{expression}"
        facts.append(FinancialFact(
            fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
            security_id=security_id, metric=current.metric, value=value,
            unit=current.unit, period_start=quarter_start,
            period_end=current.period_end, period_type="quarter",
            available_at=current.available_at, source_id=current.source_id,
            source_concept=expression,
        ))

    # Some issuers omit Q1 in the current filing but report six-month YTD and
    # the discrete second quarter. Derive the missing first quarter from that
    # internally consistent pair; longer remainders are not treated as quarters.
    for current in (fact for fact in original if fact.period_type == "ytd"):
        trailing = [
            fact for fact in direct
            if fact.metric == current.metric
            and fact.period_end == current.period_end
            and fact.period_start > current.period_start
            and fact.source_id == current.source_id
            and fact.available_at == current.available_at
        ]
        if len({(fact.value, fact.period_start, fact.unit) for fact in trailing}) != 1:
            continue
        trailing_fact = sorted(trailing, key=lambda fact: fact.fact_id)[0]
        prefix_end = trailing_fact.period_start - timedelta(days=1)
        prefix_days = (prefix_end - current.period_start).days + 1
        if not 60 <= prefix_days <= 110:
            continue
        if any(
            fact.metric == current.metric
            and fact.period_start == current.period_start
            and fact.period_end == prefix_end
            and fact.available_at == current.available_at
            for fact in direct
        ):
            continue
        if current.metric == "diluted_shares":
            current_days = (current.period_end - current.period_start).days + 1
            trailing_days = (trailing_fact.period_end - trailing_fact.period_start).days + 1
            value = (current.value * current_days - trailing_fact.value * trailing_days) / prefix_days
        else:
            value = current.value - trailing_fact.value
        if current.metric in {"capital_expenditure", "interest_expense"} and value < 0:
            continue
        if current.metric == "diluted_shares" and value <= 0:
            continue
        expression = f"derived:discrete-quarter({current.fact_id}-{trailing_fact.fact_id})"
        identity = f"{security_id}/{current.metric}/{current.period_start}/{prefix_end}/{current.available_at}/{value}/{expression}"
        facts.append(FinancialFact(
            fact_id="sec-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
            security_id=security_id, metric=current.metric, value=value,
            unit=current.unit, period_start=current.period_start,
            period_end=prefix_end, period_type="quarter",
            available_at=current.available_at, source_id=current.source_id,
            source_concept=expression,
        ))


def _instant_at_cutoff(raw: dict, as_of: date) -> bool:
    if raw.get("form") not in {"10-K", "10-Q"} or not {"end", "filed", "accn", "val"} <= raw.keys():
        return False
    return "start" not in raw and date.fromisoformat(raw["end"]) <= as_of and date.fromisoformat(raw["filed"]) <= as_of


def _quarterly_period_type(raw: dict, as_of: date) -> str | None:
    if raw.get("form") not in {"10-K", "10-Q"} or not {"start", "end", "filed", "accn", "val"} <= raw.keys():
        return None
    end, filed = date.fromisoformat(raw["end"]), date.fromisoformat(raw["filed"])
    if end > as_of or filed > as_of:
        return None
    days = (end - date.fromisoformat(raw["start"])).days + 1
    if 60 <= days <= 110:
        return "quarter"
    if raw["form"] == "10-Q" and 111 <= days <= 300:
        return "ytd"
    return None


def _annual_at_cutoff(raw: dict, as_of: date) -> bool:
    if raw.get("form") != "10-K" or not {"end", "filed", "accn", "val"} <= raw.keys():
        return False
    end, filed = date.fromisoformat(raw["end"]), date.fromisoformat(raw["filed"])
    if end > as_of or filed > as_of:
        return False
    if "start" not in raw:
        return False
    days = (end - date.fromisoformat(raw["start"])).days + 1
    return 330 <= days <= 400


def load_sec_payloads(assignments: list[str]) -> dict[str, dict]:
    payloads = {}
    for assignment in assignments:
        ticker, separator, filename = assignment.partition("=")
        if not separator or not ticker or not filename or ticker in payloads:
            raise ValueError("--company-facts must be unique TICKER=path assignments")
        payloads[ticker.upper()] = json.loads(Path(filename).read_text(encoding="utf-8"))
    return payloads
