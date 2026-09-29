"""Validation for the sourced, dated market-data CSV boundary."""

from contextlib import redirect_stdout
import csv
from dataclasses import replace
from datetime import date
import io
from pathlib import Path
import tempfile
import unittest

from stocks_infer.cli import main
from stocks_infer.research.engine import research_watchlist
from stocks_infer.research.io import load_bundle
from stocks_infer.research.market_csv import MARKET_CSV_COLUMNS, import_market_csv


FIXTURE = Path(__file__).parent / "fixtures" / "research_watchlist.json"


class MarketCsvTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load_bundle(FIXTURE)

    def test_import_preserves_separate_price_and_share_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "market.csv"
            _write_csv(path, [_row()])
            imported = import_market_csv(self.bundle, path)

        observation = next(price for price in imported.prices if price.source_id == "market:closing-price")
        self.assertEqual(observation.share_source_id, "filing:share-count")
        self.assertEqual(observation.security_id, "steady")
        self.assertEqual(observation.close, 11.25)
        result = next(
            item for item in research_watchlist(imported, date(2026, 9, 20))
            if item.ticker == "STEADY"
        )
        self.assertEqual(result.market, observation)
        self.assertFalse(any("Price is missing" in warning for warning in result.warnings))
        self.assertEqual(
            set(result.valuation[0]["market_source_ids"]),
            {"market:closing-price", "filing:share-count"},
        )

    def test_adjusted_price_and_incomplete_cohort_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "market.csv"
            adjusted = _row()
            adjusted["adjustment"] = "split_adjusted"
            _write_csv(path, [adjusted])
            with self.assertRaisesRegex(ValueError, "unadjusted"):
                import_market_csv(self.bundle, path)

            _write_csv(path, [_row()])
            with self.assertRaisesRegex(ValueError, "missing required tickers"):
                import_market_csv(self.bundle, path, require_all=True)

    def test_bundle_rejects_unknown_share_count_source(self):
        changed = replace(self.bundle.prices[0], share_source_id="missing-source")
        with self.assertRaisesRegex(ValueError, "unknown security or source"):
            replace(self.bundle, prices=(changed,) + self.bundle.prices[1:])

    def test_cli_writes_new_bundle_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, output = root / "market.csv", root / "bundle.json"
            _write_csv(path, [_row()])
            with redirect_stdout(io.StringIO()):
                code = main([
                    "import-market-csv",
                    "--input", str(FIXTURE),
                    "--market-csv", str(path),
                    "--output", str(output),
                ])
            self.assertEqual(code, 0)
            self.assertTrue(any(price.source_id == "market:closing-price" for price in load_bundle(output).prices))
            with self.assertRaises(FileExistsError):
                main([
                    "import-market-csv",
                    "--input", str(FIXTURE),
                    "--market-csv", str(path),
                    "--output", str(output),
                ])


def _row() -> dict[str, str]:
    return {
        "ticker": "STEADY",
        "price_date": "2026-09-19",
        "available_at": "2026-09-20",
        "close": "11.25",
        "currency": "USD",
        "adjustment": "unadjusted",
        "shares_outstanding": "9900000",
        "share_count_date": "2026-09-10",
        "price_source_id": "market:closing-price",
        "price_source_title": "Recorded exchange close",
        "price_source_url": "https://example.com/prices/steady",
        "price_source_published_at": "2026-09-19",
        "price_source_retrieved_at": "2026-09-20",
        "share_source_id": "filing:share-count",
        "share_source_title": "Recorded share-count filing",
        "share_source_url": "https://example.com/filings/steady",
        "share_source_published_at": "2026-09-11",
        "share_source_retrieved_at": "2026-09-20",
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=MARKET_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
