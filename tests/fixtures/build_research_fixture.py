"""Regenerate the explicitly synthetic research watchlist; no network data."""

import json
from pathlib import Path


def build():
    bundle = {"schema_version": 1, "companies": [], "sources": [], "facts": [], "prices": [], "theses": [], "scenarios": []}
    cases = {
        "STEADY": "Established profitable business with consistent cash conversion",
        "EXPAND": "Expansion capex creates temporary negative free cash flow",
        "MISSING": "Latest cash-flow disclosure is unavailable",
        "BUYBACK": "Negative book equity requires capital-return interpretation",
        "CYCLE": "Cyclical earnings require a different framework",
        "BANK": "Bank accounting requires a specialized framework",
        "THIN": "Only two annual periods are available",
        "STRESS": "Profitable history but current interest coverage below one",
        "DILUTE": "Increasing share count requires investigation",
        "RECOVER": "One year of operating losses does not erase profitable history",
    }
    for year in range(2020, 2026):
        published = f"{year + 1}-03-01"
        bundle["sources"].append({"source_id": f"synthetic-{year}", "title": f"Synthetic annual statements {year} — invented demonstration data", "url": f"https://example.com/synthetic/{year}", "published_at": published, "retrieved_at": published, "accession": None})
    bundle["sources"].append({"source_id": "synthetic-price", "title": "Synthetic market observations — invented demonstration data", "url": "https://example.com/synthetic/market", "published_at": "2026-09-18", "retrieved_at": "2026-09-18", "accession": None})
    for ticker, reason in cases.items():
        bundle["companies"].append({"security_id": ticker.lower(), "ticker": ticker, "name": f"{ticker.title()} Synthetic Company", "currency": "USD", "business_type": "bank" if ticker == "BANK" else "operating", "classification_reason": reason, "classified_at": "2026-03-01", "cyclical": ticker == "CYCLE"})
        for year in range(2020, 2026):
            if ticker == "THIN" and year < 2024:
                continue
            revenue = round(100_000_000 * 1.08 ** (year - 2020), 2)
            values = {
                "revenue": revenue, "operating_income": revenue * .2,
                "net_income": revenue * .14, "operating_cash_flow": revenue * .18,
                "capital_expenditure": revenue * .06, "interest_expense": revenue * .02,
                "diluted_shares": 10_000_000, "cash": 20_000_000,
                "debt": 40_000_000, "equity": 80_000_000, "assets": 160_000_000,
            }
            if ticker == "BUYBACK":
                values["equity"] = -30_000_000
            if year == 2025:
                if ticker == "EXPAND":
                    values["capital_expenditure"] = revenue * .25
                if ticker == "MISSING":
                    del values["operating_cash_flow"]
                if ticker == "STRESS":
                    values["interest_expense"] = revenue * .30
                if ticker == "DILUTE":
                    values["diluted_shares"] = 12_000_000
                if ticker == "RECOVER":
                    values["operating_income"] = -revenue * .02
                    values["net_income"] = -revenue * .03
            for metric, value in values.items():
                instant = metric in {"cash", "debt", "equity", "assets"}
                bundle["facts"].append({"fact_id": f"{ticker}-{year}-{metric}", "security_id": ticker.lower(), "metric": metric, "value": value, "unit": "shares" if metric == "diluted_shares" else "USD", "period_start": None if instant else f"{year}-01-01", "period_end": f"{year}-12-31", "period_type": "instant" if instant else "annual", "available_at": f"{year + 1}-03-01", "source_id": f"synthetic-{year}", "source_concept": f"synthetic:{metric}"})
        bundle["prices"].append({"security_id": ticker.lower(), "price_date": "2026-09-18", "available_at": "2026-09-18", "close": 10, "shares_outstanding": 12_000_000 if ticker == "DILUTE" else 10_000_000, "share_count_date": "2026-09-18", "currency": "USD", "source_id": "synthetic-price", "adjustment": "unadjusted"})
        bundle["theses"].append({"security_id": ticker.lower(), "version": "1", "authored_at": "2026-09-18", "business_description": "Invented operating business used to test the research workflow; not an actual investment.", "opportunity": reason, "decision": "research", "next_review": "2026-12-01", "claims": [{"claim_id": "durability", "text": "Historical economics could persist over the next five years", "assumption": True, "source_ids": ["synthetic-2025"], "counterargument": "Competition or poor reinvestment could reduce future margins", "metric": "operating_margin", "expected_outcome": "Operating margins recover or remain around 20%", "review_on": "2026-12-01", "invalidated_by": "Sustained margin decline without improving returns on investment"}]})
        for name, growth, margin in (("bear", .02, .12), ("base", .06, .20), ("bull", .10, .24)):
            bundle["scenarios"].append({"security_id": ticker.lower(), "name": name, "authored_at": "2026-09-18", "thesis_version": "1", "claim_ids": ["durability"], "rationale": "Synthetic assumptions for exercising cash-flow calculations; not forecasts.", "revenue_growth": [growth] * 5, "operating_margins": [margin] * 5, "tax_rate": .25, "sales_to_capital": 2, "discount_rate": .10, "terminal_growth": .025, "terminal_roic": .15})
    return bundle


if __name__ == "__main__":
    Path(__file__).with_name("research_watchlist.json").write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
