from datetime import date
from pathlib import Path
import unittest

from stocks_infer.research.features import History, build_features, build_ttm_features
from stocks_infer.research.sec_companyfacts import companyfacts_bundle
from stocks_infer.research.universe import UniverseCompany, load_universe, match_sec_identifiers


WORKBOOK = Path(__file__).resolve().parents[1] / "company_universe" / "growth-value-company-universe.xlsx"


class UniverseWorkbookTests(unittest.TestCase):
    @unittest.skipUnless(WORKBOOK.exists(), "user workbook is not present in this checkout")
    def test_user_universe_preserves_development_and_holdout_split(self):
        companies = load_universe(WORKBOOK)
        self.assertEqual(len(companies), 100)
        self.assertEqual(sum(c.test_set == "Development" for c in companies), 30)
        self.assertEqual(sum(c.test_set == "Evaluation" for c in companies), 60)
        self.assertEqual(sum(c.test_set == "Difficult case" for c in companies), 10)
        self.assertEqual(len({c.ticker for c in companies}), 100)

    def test_sec_match_requires_exact_exchange(self):
        company = _company("WSM", "Development")
        sec = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[719955, "WILLIAMS SONOMA INC", "WSM", "NYSE"]]}
        self.assertEqual(match_sec_identifiers((company,), sec), {"WSM": 719955})
        with self.assertRaisesRegex(ValueError, "needs review"):
            match_sec_identifiers((company,), {**sec, "data": [[719955, "WILLIAMS SONOMA INC", "WSM", "Nasdaq"]]})


class SecCompanyFactsTests(unittest.TestCase):
    def test_ytd_facts_derive_discrete_quarters_and_ttm_without_double_counting(self):
        def row(start, end, value, filed, accession, form="10-Q"):
            return {"start": start, "end": end, "val": value, "filed": filed, "accn": accession, "form": form}

        revenue = [
            row("2024-01-01", "2024-12-31", 80, "2025-02-01", "0000000001-25-000001", "10-K"),
            row("2025-01-01", "2025-03-31", 20, "2025-05-01", "0000000001-25-000002"),
            row("2025-04-01", "2025-06-30", 25, "2025-08-01", "0000000001-25-000003"),
            row("2025-01-01", "2025-06-30", 45, "2025-08-01", "0000000001-25-000003"),
            row("2025-07-01", "2025-09-30", 30, "2025-11-01", "0000000001-25-000004"),
            row("2025-01-01", "2025-09-30", 75, "2025-11-01", "0000000001-25-000004"),
            row("2025-01-01", "2025-12-31", 100, "2026-02-01", "0000000001-26-000001", "10-K"),
        ]
        cash_flow = [
            row("2024-01-01", "2024-12-31", 24, "2025-02-01", "0000000001-25-000001", "10-K"),
            row("2025-01-01", "2025-03-31", 5, "2025-05-01", "0000000001-25-000002"),
            row("2025-01-01", "2025-06-30", 12, "2025-08-01", "0000000001-25-000003"),
            row("2025-01-01", "2025-09-30", 20, "2025-11-01", "0000000001-25-000004"),
            row("2025-01-01", "2025-12-31", 30, "2026-02-01", "0000000001-26-000001", "10-K"),
        ]
        payload = {"cik": 6951, "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": revenue}},
            "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": cash_flow}},
        }}}
        bundle = companyfacts_bundle(
            (_company("AMAT", "Development"),), {"AMAT": 6951}, {"AMAT": payload},
            as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20),
            annual_periods=2, quarterly_periods=4,
        )
        history = History(bundle.facts, bundle.companies[0].security_id, date(2026, 9, 20))
        derived_cash = sorted(
            (
                fact for fact in bundle.facts
                if fact.metric == "operating_cash_flow" and fact.period_type == "quarter"
            ),
            key=lambda fact: fact.period_end,
        )
        self.assertEqual([fact.value for fact in derived_cash], [5, 7, 8, 10])
        self.assertTrue(all("derived:discrete-quarter" in fact.source_concept for fact in derived_cash[1:]))
        ttm = [feature for feature in build_ttm_features(history, "USD") if feature.period_end == date(2025, 12, 31)]
        self.assertEqual(next(feature for feature in ttm if feature.name == "revenue").value, 100)
        self.assertEqual(next(feature for feature in ttm if feature.name == "operating_cash_flow").value, 30)

    def test_reconciled_debt_sums_components_from_same_filing(self):
        annual = [
            {"start": "2024-01-01", "end": "2024-12-31", "val": 100, "filed": "2025-03-01", "accn": "0000000001-25-000001", "form": "10-K"},
            {"start": "2025-01-01", "end": "2025-12-31", "val": 110, "filed": "2026-03-01", "accn": "0000000001-26-000001", "form": "10-K"},
        ]
        current = [
            {"end": row["end"], "val": value, "filed": row["filed"], "accn": row["accn"], "form": "10-K"}
            for row, value in zip(annual, (10, 20))
        ]
        noncurrent = [
            {"end": row["end"], "val": value, "filed": row["filed"], "accn": row["accn"], "form": "10-K"}
            for row, value in zip(annual, (90, 80))
        ]
        payload = {"cik": 6951, "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": annual}},
            "LongTermDebtNoncurrent": {"units": {"USD": noncurrent}},
            "ShortTermBorrowings": {"units": {"USD": current}},
        }}}
        bundle = companyfacts_bundle((_company("AMAT", "Development"),), {"AMAT": 6951}, {"AMAT": payload}, as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2)
        debt = [fact for fact in bundle.facts if fact.metric == "debt"]
        self.assertEqual([fact.value for fact in debt], [100, 100])
        self.assertTrue(all(fact.source_concept.startswith("derived:sum(") for fact in debt))

    def test_qcom_prefers_reported_total_and_falls_back_to_quarterly_components(self):
        annual = [
            {"start": "2023-10-01", "end": "2024-09-29", "val": 100, "filed": "2024-11-01", "accn": "0000000001-24-000001", "form": "10-K"},
            {"start": "2024-09-30", "end": "2025-09-28", "val": 110, "filed": "2025-11-01", "accn": "0000000001-25-000001", "form": "10-K"},
            {"start": "2025-09-29", "end": "2025-12-28", "val": 30, "filed": "2026-02-01", "accn": "0000000001-26-000001", "form": "10-Q"},
        ]
        total = [
            {"end": "2025-09-28", "val": 100, "filed": "2025-11-01", "accn": "0000000001-25-000001", "form": "10-K"},
        ]
        current = [
            {"end": "2025-09-28", "val": 20, "filed": "2025-11-01", "accn": "0000000001-25-000001", "form": "10-K"},
            {"end": "2025-12-28", "val": 30, "filed": "2026-02-01", "accn": "0000000001-26-000001", "form": "10-Q"},
        ]
        noncurrent = [
            {"end": "2025-09-28", "val": 90, "filed": "2025-11-01", "accn": "0000000001-25-000001", "form": "10-K"},
            {"end": "2025-12-28", "val": 80, "filed": "2026-02-01", "accn": "0000000001-26-000001", "form": "10-Q"},
        ]
        payload = {"cik": 804328, "facts": {"us-gaap": {
            "Revenues": {"units": {"USD": annual}},
            "DebtLongtermAndShorttermCombinedAmount": {"units": {"USD": total}},
            "DebtCurrent": {"units": {"USD": current}},
            "LongTermDebt": {"units": {"USD": noncurrent}},
        }}}
        bundle = companyfacts_bundle(
            (_company("QCOM", "Development"),), {"QCOM": 804328}, {"QCOM": payload},
            as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2,
        )
        debt = {(fact.period_end, fact.available_at): fact for fact in bundle.facts if fact.metric == "debt"}
        annual_debt = debt[(date(2025, 9, 28), date(2025, 11, 1))]
        quarter_debt = debt[(date(2025, 12, 28), date(2026, 2, 1))]
        self.assertEqual((annual_debt.value, annual_debt.source_concept), (100, "us-gaap:DebtLongtermAndShorttermCombinedAmount"))
        self.assertEqual(quarter_debt.value, 110)
        self.assertTrue(quarter_debt.source_concept.startswith("derived:sum("))

    def test_filing_reconciled_zero_debt_is_not_inferred_from_missing_tag(self):
        annual = [
            {"start": "2024-02-03", "end": "2025-02-02", "val": 100, "filed": "2025-03-20", "accn": "0000000001-25-000001", "form": "10-K"},
            {"start": "2025-02-03", "end": "2026-02-01", "val": 110, "filed": "2026-03-20", "accn": "0000000001-26-000001", "form": "10-K"},
        ]
        payload = {"cik": 719955, "facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": annual}}}}}
        bundle = companyfacts_bundle((_company("WSM", "Development"),), {"WSM": 719955}, {"WSM": payload}, as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2)
        debt = [fact for fact in bundle.facts if fact.metric == "debt"]
        self.assertEqual([fact.value for fact in debt], [0, 0])
        self.assertEqual({fact.source_concept for fact in debt}, {"reconciled:no-interest-bearing-debt"})
        features = build_features(History(bundle.facts, bundle.companies[0].security_id, date(2026, 9, 20)), "USD")
        coverage = next(f for f in reversed(features) if f.name == "interest_coverage")
        self.assertEqual(coverage.status, "not_meaningful")

    def test_reviewed_filing_lines_fill_companyfacts_extension_gaps(self):
        qcom_annual = [
            {"start": "2023-09-25", "end": "2024-09-29", "val": 100, "filed": "2025-11-05", "accn": "0000804328-25-000085", "form": "10-K"},
            {"start": "2024-09-30", "end": "2025-09-28", "val": 110, "filed": "2025-11-05", "accn": "0000804328-25-000085", "form": "10-K"},
        ]
        qcom_payload = {"cik": 804328, "facts": {"us-gaap": {"Revenues": {"units": {"USD": qcom_annual}}}}}
        qcom = companyfacts_bundle(
            (_company("QCOM", "Development"),), {"QCOM": 804328}, {"QCOM": qcom_payload},
            as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2,
        )
        capex = [fact for fact in qcom.facts if fact.metric == "capital_expenditure"]
        self.assertEqual([fact.value for fact in capex], [1_041_000_000, 1_192_000_000])
        self.assertEqual({fact.source_concept for fact in capex}, {"filing-line:Capital expenditures"})

        coke_annual = [
            {"start": "2024-01-01", "end": "2024-12-31", "val": 100, "filed": "2026-02-18", "accn": "0001628280-26-009057", "form": "10-K"},
            {"start": "2025-01-01", "end": "2025-12-31", "val": 110, "filed": "2026-02-18", "accn": "0001628280-26-009057", "form": "10-K"},
        ]
        coke_payload = {"cik": 317540, "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": coke_annual}},
        }}}
        coke = companyfacts_bundle(
            (_company("COKE", "Development"),), {"COKE": 317540}, {"COKE": coke_payload},
            as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2,
        )
        interest = [fact for fact in coke.facts if fact.metric == "interest_expense"]
        shares = [fact for fact in coke.facts if fact.metric == "diluted_shares"]
        self.assertEqual([fact.value for fact in interest], [62_000_000, 102_900_000])
        self.assertEqual([fact.value for fact in shares], [90_524_000, 83_807_000])

    def test_development_uses_total_revenue_and_routes_cyclical_business(self):
        annual = [
            {"start": "2024-01-01", "end": "2024-12-31", "val": 100, "filed": "2025-03-01", "accn": "0000000001-25-000001", "form": "10-K"},
            {"start": "2025-01-01", "end": "2025-12-31", "val": 110, "filed": "2026-03-01", "accn": "0000000001-26-000001", "form": "10-K"},
        ]
        component = [{**row, "val": row["val"] / 10} for row in annual]
        payload = {"cik": 821026, "facts": {"us-gaap": {
            "Revenues": {"units": {"USD": annual}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": component}},
        }}}
        bundle = companyfacts_bundle((_company("ANDE", "Development"),), {"ANDE": 821026}, {"ANDE": payload}, as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2)
        self.assertTrue(bundle.companies[0].cyclical)
        self.assertEqual({f.source_concept for f in bundle.facts}, {"us-gaap:Revenues"})
        self.assertEqual(History(bundle.facts, bundle.companies[0].security_id, date(2026, 9, 20)).get("revenue", date(2025, 12, 31)).value, 110)

    def test_specialized_company_keeps_annual_facts_without_revenue(self):
        annual = [
            {"start": "2024-01-01", "end": "2024-12-31", "val": 100, "filed": "2025-03-01", "accn": "0000000001-25-000001", "form": "10-K"},
            {"start": "2025-01-01", "end": "2025-12-31", "val": 110, "filed": "2026-03-01", "accn": "0000000001-26-000001", "form": "10-K"},
        ]
        payload = {"cik": 1253986, "facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": annual}}}}}
        bundle = companyfacts_bundle((_company("ABR", "Development"),), {"ABR": 1253986}, {"ABR": payload}, as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2)
        self.assertEqual(bundle.companies[0].business_type, "reit")
        features = build_features(History(bundle.facts, bundle.companies[0].security_id, date(2026, 9, 20)), "USD")
        latest = {f.name: f for f in features if f.period_end == date(2025, 12, 31)}
        self.assertEqual(latest["net_income"].value, 110)
        self.assertIsNone(latest["revenue"].value)

    def test_annual_facts_keep_filing_dates_and_later_revision(self):
        annual = [
            {"start": "2023-01-01", "end": "2023-12-31", "val": 100, "filed": "2024-03-01", "accn": "0000000001-24-000001", "form": "10-K"},
            {"start": "2024-01-01", "end": "2024-12-31", "val": 110, "filed": "2025-03-01", "accn": "0000000001-25-000001", "form": "10-K"},
            {"start": "2024-01-01", "end": "2024-12-31", "val": 115, "filed": "2026-03-01", "accn": "0000000001-26-000001", "form": "10-K"},
            {"start": "2024-01-01", "end": "2024-12-31", "val": 999, "filed": "2025-06-01", "accn": "0000000001-25-000002", "form": "10-Q"},
        ]
        payload = {"cik": 719955, "facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": annual}}}}}
        company = _company("WSM", "Development")
        bundle = companyfacts_bundle((company,), {"WSM": 719955}, {"WSM": payload}, as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20), annual_periods=2)
        self.assertEqual(len(bundle.facts), 3)
        self.assertEqual(History(bundle.facts, bundle.companies[0].security_id, date(2025, 9, 20)).get("revenue", date(2024, 12, 31)).value, 110)
        self.assertEqual(History(bundle.facts, bundle.companies[0].security_id, date(2026, 9, 20)).get("revenue", date(2024, 12, 31)).value, 115)
        self.assertTrue(all(f.source_concept.startswith("us-gaap:") for f in bundle.facts))
        self.assertTrue(any(s.accession == "0000000001-26-000001" for s in bundle.sources))

    def test_held_out_company_is_rejected_before_import(self):
        with self.assertRaisesRegex(ValueError, "held out"):
            companyfacts_bundle((_company("WSM", "Evaluation"),), {"WSM": 719955}, {"WSM": {"cik": 719955}}, as_of=date(2026, 9, 20), retrieved_on=date(2026, 9, 20))


def _company(ticker: str, test_set: str) -> UniverseCompany:
    return UniverseCompany(ticker, "Williams-Sonoma", "Home furnishings retail", "Sells home products", "Consumer Discretionary", "Large", "Value", test_set, "", "NYSE", "https://example.com/wsm", 10)


if __name__ == "__main__":
    unittest.main()
