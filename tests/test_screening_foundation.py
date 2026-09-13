from contextlib import redirect_stdout
from datetime import date
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

from stocks_infer.algorithms import (
    AlgorithmRegistry,
    MagicFormulaAlgorithm,
    PiotroskiFScoreAlgorithm,
)
from stocks_infer.cli import main
from stocks_infer.dataset import (
    build_screening_records,
    fingerprint_screening_records,
)
from stocks_infer.models import FinancialSnapshot, PriceSnapshot, Security
from stocks_infer.recorded_data import load_screening_records
from stocks_infer.runner import ScreeningRunner
from stocks_infer.storage import (
    ParquetSnapshotStore,
    RawResponseCache,
    StorageLayout,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "screening_records.json"


class AlgorithmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_screening_records(FIXTURE_PATH)
        cls.context_date = date(2026, 9, 12)

    def test_magic_formula_ranks_earnings_yield_and_return_on_capital(self):
        result = ScreeningRunner([MagicFormulaAlgorithm()]).run(
            self.records,
            as_of_date=self.context_date,
            shortlist_size=3,
        )
        scores = {
            score.ticker: score
            for score in result.algorithm_scores
            if score.algorithm_slug == "magic_formula"
        }

        self.assertEqual(scores["ALFA"].rank, 1)
        self.assertEqual(scores["CHAR"].rank, 2)
        self.assertEqual(scores["BRAV"].rank, 3)
        self.assertFalse(scores["DELT"].eligible)
        self.assertIn("Missing metrics", scores["DELT"].warnings[0])

    def test_piotroski_reports_all_nine_signals(self):
        result = ScreeningRunner([PiotroskiFScoreAlgorithm()]).run(
            self.records,
            as_of_date=self.context_date,
            shortlist_size=3,
        )
        scores = {
            score.ticker: score
            for score in result.algorithm_scores
            if score.algorithm_slug == "piotroski_f_score"
        }

        self.assertEqual(scores["ALFA"].metrics_used["f_score"], 9.0)
        self.assertEqual(len(scores["ALFA"].reasons), 9)
        self.assertEqual(scores["BRAV"].metrics_used["f_score"], 5.0)
        self.assertEqual(scores["CHAR"].metrics_used["f_score"], 2.0)
        self.assertFalse(scores["DELT"].eligible)

    def test_consensus_requires_all_selected_algorithms_by_default(self):
        runner = ScreeningRunner(
            [MagicFormulaAlgorithm(), PiotroskiFScoreAlgorithm()]
        )
        result = runner.run(
            self.records,
            as_of_date=self.context_date,
            shortlist_size=2,
        )

        self.assertEqual([score.ticker for score in result.shortlist], ["ALFA", "CHAR"])
        delta = next(
            score for score in result.consensus_scores if score.ticker == "DELT"
        )
        self.assertFalse(delta.eligible)


class DatasetTests(unittest.TestCase):
    def test_provider_outputs_join_on_stable_security_id(self):
        as_of_date = date(2026, 9, 12)
        security = Security("sec-1", "ONE", "One Corp", "NASDAQ")
        financial = FinancialSnapshot(
            security_id="sec-1",
            as_of_date=as_of_date,
            period_end=date(2026, 6, 30),
            available_at=date(2026, 8, 1),
            source="fundamentals-fixture",
            ebit_ttm=10.0,
        )
        price = PriceSnapshot(
            security_id="sec-1",
            as_of_date=as_of_date,
            price_date=date(2026, 9, 11),
            adjusted_close=25.0,
            source="price-fixture",
            enterprise_value=100.0,
        )

        records = build_screening_records(
            [security], [financial], [price], as_of_date
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].ticker, "ONE")
        self.assertEqual(records[0].ebit_ttm, 10.0)
        self.assertEqual(records[0].enterprise_value, 100.0)

    def test_dataset_fingerprint_is_independent_of_record_order(self):
        records = load_screening_records(FIXTURE_PATH)

        self.assertEqual(
            fingerprint_screening_records(records),
            fingerprint_screening_records(tuple(reversed(records))),
        )


class RegistryTests(unittest.TestCase):
    def test_duplicate_algorithm_slug_is_rejected(self):
        registry = AlgorithmRegistry()
        registry.register(MagicFormulaAlgorithm())

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(MagicFormulaAlgorithm())


class StorageTests(unittest.TestCase):
    def test_raw_response_cache_writes_compressed_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            layout = StorageLayout(Path(temporary_directory))
            cache = RawResponseCache(layout)
            destination = cache.write_json(
                provider="fixture-provider",
                retrieved_on=date(2026, 9, 12),
                key="AAPL/company-facts",
                payload={"ticker": "AAPL", "value": 42},
            )

            with gzip.open(destination, "rt", encoding="utf-8") as input_file:
                payload = json.load(input_file)

            self.assertEqual(payload, {"ticker": "AAPL", "value": 42})

    def test_parquet_snapshot_round_trip(self):
        records = load_screening_records(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "snapshot.parquet"
            store = ParquetSnapshotStore()
            store.write_screening_records(destination, records)
            restored = store.read_screening_records(destination)

        self.assertEqual(restored, records)

    def test_fixture_cli_writes_reproducible_run_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory)
            with redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "screen-fixture",
                        "--input",
                        str(FIXTURE_PATH),
                        "--output-root",
                        str(output_root),
                        "--shortlist-size",
                        "2",
                        "--run-id",
                        "test-run",
                    ]
                )

            run_directory = output_root / "runs" / "test-run"
            manifest = json.loads(
                (run_directory / "manifest.json").read_text(encoding="utf-8")
            )
            shortlist = (run_directory / "shortlist.csv").read_text(
                encoding="utf-8"
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(manifest["evaluated_count"], 4)
            self.assertEqual(manifest["shortlisted_count"], 2)
            self.assertEqual(len(manifest["dataset_fingerprint"]), 64)
            self.assertTrue((output_root / manifest["input_snapshot"]).exists())
            self.assertTrue((run_directory / "all_scores.parquet").exists())
            self.assertIn("ALFA", shortlist)


if __name__ == "__main__":
    unittest.main()
