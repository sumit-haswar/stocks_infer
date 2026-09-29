"""Behavioral coverage for missing evidence, dated research and reproducibility."""

from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest

from stocks_infer.cli import main
from stocks_infer.research.artifacts import compare_runs, read_verified_run, render_report, write_research_run
from stocks_infer.research.engine import research_watchlist
from stocks_infer.research.features import History, build_features
from stocks_infer.research.io import load_bundle, write_json
from stocks_infer.research.models import FinancialFact, SourceDocument
from stocks_infer.research.valuation import discounted_cash_flow, value_scenario


FIXTURE = Path(__file__).parent / "fixtures" / "research_watchlist.json"
AS_OF = date(2026, 9, 18)


class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_bundle(FIXTURE)
        cls.results = {r.ticker: r for r in research_watchlist(cls.bundle, AS_OF)}

    def latest(self, ticker, metric):
        return next(f for f in reversed(self.results[ticker].features) if f.name == metric)

    def test_negative_cash_flow_is_visible_without_excluding_company(self):
        result = self.results["EXPAND"]
        self.assertEqual(result.framework_status, "applicable")
        self.assertLess(self.latest("EXPAND", "free_cash_flow").value, 0)
        self.assertIn("investigate_weaknesses", result.lists)
        self.assertEqual(len(result.valuation), 3)
        self.assertTrue(any("no automatic exclusion" in w for w in result.warnings))

    def test_missing_cash_flow_never_becomes_zero_or_positive_quality(self):
        result = self.results["MISSING"]
        self.assertEqual(result.framework_status, "applicable")
        self.assertIsNone(self.latest("MISSING", "cash_conversion").value)
        self.assertEqual(result.assessments[0].status, "incomplete")
        self.assertIn("evidence_needed", result.lists)
        self.assertNotIn("quality_at_potentially_attractive_price", result.lists)

    def test_ttm_bridge_allows_one_week_fiscal_calendar_shift(self):
        facts = (
            FinancialFact(
                "annual", "calendar-shift", "revenue", 100, "USD",
                date(2024, 12, 31), date(2025, 2, 20), "annual-source", "reported",
                "annual", date(2024, 1, 1),
            ),
            FinancialFact(
                "prior-ytd", "calendar-shift", "revenue", 45, "USD",
                date(2024, 6, 28), date(2024, 8, 1), "prior-source", "reported",
                "ytd", date(2024, 1, 1),
            ),
            FinancialFact(
                "current-ytd", "calendar-shift", "revenue", 55, "USD",
                date(2025, 7, 4), date(2025, 8, 1), "current-source", "reported",
                "ytd", date(2025, 1, 1),
            ),
        )
        value, inputs = History(facts, "calendar-shift", date(2025, 8, 1)).ttm_bridge(
            "revenue", date(2024, 6, 29), date(2025, 7, 4)
        )
        self.assertEqual(value, 110)
        self.assertEqual({fact.fact_id for fact in inputs}, {"annual", "prior-ytd", "current-ytd"})

    def test_negative_equity_produces_nonmeaningful_return_not_poor_score(self):
        result = self.results["BUYBACK"]
        self.assertEqual(result.framework_status, "applicable")
        self.assertEqual(self.latest("BUYBACK", "pretax_return_on_capital").status, "not_meaningful")
        self.assertEqual(result.assessments[0].status, "supportive")
        self.assertEqual(result.assessments[-1].status, "available_for_annual_review")
        self.assertTrue(any("book equity" in w for w in result.warnings))

    def test_negative_equity_does_not_create_inflated_return_when_debt_is_large(self):
        facts = tuple(replace(f, value=200_000_000) if f.security_id == "buyback" and f.metric == "debt" else f for f in self.bundle.facts)
        features = build_features(History(facts, "buyback", AS_OF), "USD")
        latest = next(f for f in reversed(features) if f.name == "pretax_return_on_capital")
        self.assertEqual(latest.status, "not_meaningful")
        self.assertIsNone(latest.value)

    def test_specialized_companies_remain_visible_without_wrong_yardstick(self):
        self.assertEqual(len(self.results), 10)
        for ticker in ("BANK", "CYCLE"):
            with self.subTest(ticker=ticker):
                result = self.results[ticker]
                self.assertEqual(result.framework_status, "different_framework")
                self.assertEqual(result.assessments[0].status, "not_assessed")
                self.assertEqual(result.valuation, ())
                self.assertIn("framework_review", result.lists)
                self.assertFalse(any("scenario set is incomplete" in w for w in result.warnings))

    def test_one_loss_year_preserves_established_business_review(self):
        result = self.results["RECOVER"]
        self.assertEqual(result.framework_status, "applicable")
        self.assertEqual(self.latest("RECOVER", "cash_conversion").status, "not_meaningful")
        self.assertIn("investigate_weaknesses", result.lists)

    def test_severe_interest_concern_is_not_averaged_away(self):
        result = self.results["STRESS"]
        self.assertEqual(result.assessments[0].status, "supportive")
        self.assertTrue(any("HIGH PRIORITY" in w for w in result.warnings))
        self.assertIn("investigate_weaknesses", result.lists)
        self.assertIn("valuation_opportunity_needing_review", result.lists)
        self.assertNotIn("quality_at_potentially_attractive_price", result.lists)

    def test_hand_calculated_features_and_provenance(self):
        self.assertAlmostEqual(self.latest("STEADY", "revenue_growth").value, .08)
        self.assertAlmostEqual(self.latest("STEADY", "operating_margin").value, .2)
        self.assertAlmostEqual(self.latest("STEADY", "cash_conversion").value, 9 / 7)
        self.assertAlmostEqual(self.latest("STEADY", "interest_coverage").value, 10)
        self.assertIn("STEADY-2025-operating_income", self.latest("STEADY", "operating_margin").input_ids)
        self.assertEqual(self.latest("STEADY", "net_debt").value, 20_000_000)

    def test_future_restatement_cannot_change_historical_features(self):
        original = next(f for f in self.bundle.facts if f.fact_id == "STEADY-2025-revenue")
        source = SourceDocument("restatement", "Later correction", "https://example.com/later", date(2026, 10, 1), date(2026, 10, 1))
        amended = replace(original, fact_id="amended", value=original.value * 2, available_at=source.published_at, source_id=source.source_id)
        bundle = replace(self.bundle, facts=self.bundle.facts + (amended,), sources=self.bundle.sources + (source,))
        before = next(r for r in research_watchlist(bundle, AS_OF) if r.ticker == "STEADY")
        self.assertEqual(before, self.results["STEADY"])
        after = next(r for r in research_watchlist(bundle, date(2026, 10, 2)) if r.ticker == "STEADY")
        updated = next(f for f in reversed(after.features) if f.name == "revenue")
        self.assertEqual(updated.value, original.value * 2)
        self.assertIn("amended", updated.input_ids)
        self.assertNotIn("Later correction", render_report(before, bundle, AS_OF))

    def test_conflicting_same_date_facts_are_not_arbitrarily_selected(self):
        original = next(f for f in self.bundle.facts if f.fact_id == "STEADY-2025-revenue")
        conflict = replace(original, fact_id="conflict", value=original.value * 2)
        features = build_features(History(self.bundle.facts + (conflict,), "steady", AS_OF), "USD")
        current = next(f for f in reversed(features) if f.name == "revenue")
        self.assertEqual(current.status, "invalid")
        self.assertIsNone(current.value)

    def test_future_thesis_and_classification_are_not_used(self):
        company = replace(self.bundle.companies[0], classified_at=date(2027, 1, 1), classification_reason="FUTURE_CLASSIFICATION")
        thesis = replace(self.bundle.theses[0], version="future", authored_at=date(2027, 1, 1), opportunity="FUTURE_OPPORTUNITY")
        bundle = replace(self.bundle, companies=(company,) + self.bundle.companies[1:], theses=self.bundle.theses + (thesis,))
        result = next(r for r in research_watchlist(bundle, AS_OF) if r.security_id == company.security_id)
        report = render_report(result, bundle, AS_OF)
        self.assertNotIn("FUTURE_CLASSIFICATION", report)
        self.assertNotIn("FUTURE_OPPORTUNITY", report)
        self.assertEqual(result.framework_status, "needs_review")

    def test_quarterly_or_ytd_values_cannot_replace_annual_revenue(self):
        original = next(f for f in self.bundle.facts if f.fact_id == "STEADY-2025-revenue")
        quarterly = replace(original, fact_id="quarter", period_type="quarter", period_start=date(2025, 10, 1), value=1, available_at=AS_OF)
        actual = History(self.bundle.facts + (quarterly,), "steady", AS_OF).get("revenue", date(2025, 12, 31))
        self.assertEqual(actual, original)

    def test_misaligned_annual_intervals_produce_invalid_feature(self):
        facts = tuple(replace(f, period_start=date(2025, 1, 2)) if f.fact_id == "STEADY-2025-net_income" else f for f in self.bundle.facts)
        features = build_features(History(facts, "steady", AS_OF), "USD")
        current = next(f for f in reversed(features) if f.name == "cash_conversion")
        self.assertEqual(current.status, "invalid")

    def test_missing_revenue_does_not_hide_independent_balance_sheet_facts(self):
        facts = tuple(f for f in self.bundle.facts if f.fact_id != "STEADY-2025-revenue")
        features = build_features(History(facts, "steady", AS_OF), "USD")
        latest = {f.name: f for f in features if f.period_end == date(2025, 12, 31)}
        self.assertEqual(latest["revenue"].status, "missing")
        self.assertEqual(latest["cash"].value, 20_000_000)
        self.assertEqual(latest["net_debt"].value, 20_000_000)
        self.assertEqual(latest["net_debt"].input_ids, ("STEADY-2025-cash", "STEADY-2025-debt"))

    def test_fifty_three_week_comparison_warns_without_inventing_adjusted_growth(self):
        facts = tuple(replace(f, period_start=date(2024, 12, 25)) if f.fact_id == "STEADY-2025-revenue" else f for f in self.bundle.facts)
        features = build_features(History(facts, "steady", AS_OF), "USD")
        latest = next(f for f in reversed(features) if f.name == "revenue_growth")
        self.assertAlmostEqual(latest.value, .08)
        self.assertTrue(any("not week-adjusted" in warning for warning in latest.warnings))

    def test_stale_price_does_not_enter_price_opportunity_queue(self):
        results = research_watchlist(self.bundle, date(2026, 10, 1))
        result = next(r for r in results if r.ticker == "STEADY")
        self.assertIn("evidence_needed", result.lists)
        self.assertNotIn("quality_at_potentially_attractive_price", result.lists)

    def test_nonfinite_values_and_currency_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            replace(self.bundle.facts[0], value=float("nan"))
        with self.assertRaisesRegex(ValueError, "currency/unit"):
            replace(self.bundle, facts=(replace(self.bundle.facts[0], unit="EUR"),))

    def test_claims_need_sources_or_explicit_assumption_and_no_future_evidence(self):
        thesis = self.bundle.theses[0]
        claim = replace(thesis.claims[0], assumption=False, source_ids=())
        with self.assertRaisesRegex(ValueError, "evidence"):
            replace(self.bundle, theses=(replace(thesis, claims=(claim,)),))
        with self.assertRaisesRegex(ValueError, "future source"):
            replace(self.bundle, theses=(replace(thesis, authored_at=date(2020, 1, 1)),))

    def test_market_conflict_withholds_valuation_and_adjusted_price_rejected(self):
        price = self.bundle.prices[0]
        with self.assertRaisesRegex(ValueError, "unadjusted"):
            replace(price, adjustment="total_return")
        bundle = replace(self.bundle, prices=self.bundle.prices + (replace(price, close=99),))
        result = next(r for r in research_watchlist(bundle, AS_OF) if r.security_id == price.security_id)
        self.assertEqual(result.valuation, ())
        self.assertTrue(any("Conflicting market" in w for w in result.warnings))


class ValuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = load_bundle(FIXTURE).scenarios[1]

    def test_constant_cash_flow_matches_perpetuity_and_equity_bridge(self):
        scenario = replace(self.scenario, revenue_growth=(0,) * 5, operating_margins=(.2,) * 5, terminal_growth=0)
        # Revenue 100, margin 20%, tax 25% => FCFF 15 forever.
        # EV = 15 / 10% = 150; equity = 150 - 20; / 10 shares = 13.
        result = discounted_cash_flow(scenario, revenue=100, net_debt=20, shares=10, price=10)
        self.assertAlmostEqual(result["enterprise_value"], 150)
        self.assertAlmostEqual(result["per_share"], 13)
        self.assertAlmostEqual(result["upside"], .3)

    def test_growth_requires_reinvestment_and_sensitivity_is_monotonic(self):
        result = value_scenario(self.scenario, revenue=100, net_debt=20, shares=10, price=10)
        # First-year growth 6%; sales/capital 2 => investment 3.
        self.assertAlmostEqual(result["projection"][0]["reinvestment"], 3)
        values = [s["per_share"] for s in result["sensitivity"]]
        self.assertGreater(values[0], values[1])
        self.assertGreater(values[1], values[2])

    def test_invalid_terminal_assumptions_fail_explicitly(self):
        with self.assertRaises(ValueError):
            replace(self.scenario, terminal_growth=.10)
        with self.assertRaisesRegex(ValueError, "terminal profitability"):
            discounted_cash_flow(replace(self.scenario, operating_margins=(-.1,) * 5), revenue=100, net_debt=20, shares=10, price=10)


class ResearchArtifactTests(unittest.TestCase):
    def test_cli_reports_replay_parquet_and_preserves_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with redirect_stdout(io.StringIO()):
                code = main(["research", "--input", str(FIXTURE), "--as-of", str(AS_OF), "--output-root", tmp, "--run-id", "first"])
            self.assertEqual(code, 0)
            first = root / "research_runs" / "first"
            manifest, results = read_verified_run(first)
            self.assertEqual(manifest["evaluated_count"], 10)
            self.assertEqual(len(list(first.glob("company-*.md"))), 10)
            self.assertTrue((first / "market.parquet").is_file())
            import duckdb
            with duckdb.connect() as connection:
                rows = connection.execute("SELECT status, value FROM read_parquet(?) WHERE security_id='missing' AND feature='cash_conversion' ORDER BY period_end DESC LIMIT 1", [str(first / "features.parquet")]).fetchone()
                market_sources = connection.execute(
                    "SELECT price_source_id, share_source_id FROM read_parquet(?) WHERE security_id='steady'",
                    [str(first / "market.parquet")],
                ).fetchone()
            self.assertEqual(rows, ("missing", None))
            self.assertEqual(market_sources, ("synthetic-price", "synthetic-price"))
            replay = write_research_run(first / "input.json", root, AS_OF, "replay")
            self.assertEqual(results, read_verified_run(replay)[1])
            self.assertEqual(compare_runs(first, replay)["companies"], [])
            with self.assertRaises(FileExistsError):
                write_research_run(FIXTURE, root, AS_OF, "first")
            (first / "research.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed"):
                read_verified_run(first)

    def test_comparison_identifies_market_change_without_financial_change(self):
        bundle = load_bundle(FIXTURE)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_research_run(FIXTURE, root, AS_OF, "first")
            altered = replace(bundle, prices=(replace(bundle.prices[0], close=11),) + bundle.prices[1:])
            write_json(root / "changed.json", altered)
            second = write_research_run(root / "changed.json", root, AS_OF, "second")
            changes = compare_runs(first, second)["companies"]
            self.assertEqual(len(changes), 1)
            self.assertIn("market_data", changes[0]["changes"])
            self.assertNotIn("financial_evidence", changes[0]["changes"])


if __name__ == "__main__":
    unittest.main()
