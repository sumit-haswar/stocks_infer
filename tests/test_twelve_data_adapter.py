"""Tests for the Twelve Data plus SEC market adapter."""

from datetime import date
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from stocks_infer.research.market_csv import import_market_csv
from stocks_infer.research.models import Company, ResearchBundle, SourceDocument
from stocks_infer.research.twelve_data import TwelveDataError
from stocks_infer.research.twelve_data_adapter import (
    build_twelve_data_market_rows,
    select_sec_outstanding_shares,
    write_twelve_data_market_csv,
)
from stocks_infer.storage import RawResponseCache, StorageLayout


ACCESSION = "0000000123-26-000045"


class _RecordedClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def daily_time_series(self, ticker, start_date, end_date):
        self.calls.append((ticker, start_date, end_date))
        return (
            self.payload,
            "https://api.twelvedata.com/time_series?"
            f"symbol={ticker}&interval=1day&adjust=none",
        )


class TwelveDataAdapterTests(unittest.TestCase):
    def setUp(self):
        self.company = Company(
            security_id="cik:0000000123",
            ticker="AMAT",
            name="Test Company",
            currency="USD",
            business_type="operating",
            classification_reason="Recorded adapter fixture.",
            classified_at=date(2026, 9, 20),
        )
        self.sec_source = SourceDocument(
            source_id=f"sec:{ACCESSION}",
            title=f"SEC Form 10-Q {ACCESSION} for AMAT",
            url=(
                "https://www.sec.gov/Archives/edgar/data/123/"
                f"{ACCESSION.replace('-', '')}/{ACCESSION}-index.htm"
            ),
            published_at=date(2026, 8, 15),
            retrieved_at=date(2026, 9, 20),
            accession=ACCESSION,
        )
        self.bundle = ResearchBundle(
            companies=(self.company,),
            sources=(self.sec_source,),
            facts=(),
            prices=(),
        )

    def test_builds_importable_row_and_caches_credential_free_response(self):
        client = _RecordedClient(_price_payload("AMAT"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = build_twelve_data_market_rows(
                self.bundle,
                {"AMAT": _companyfacts()},
                client,
                as_of=date(2026, 9, 26),
                retrieved_on=date(2026, 9, 27),
                raw_cache=RawResponseCache(StorageLayout(root)),
            )
            output = root / "market.csv"
            write_twelve_data_market_csv(output, rows)
            imported = import_market_csv(self.bundle, output, require_all=True)

            caches = list((root / "data" / "raw").rglob("*.json.gz"))
            self.assertEqual(len(caches), 1)
            with gzip.open(caches[0], "rt", encoding="utf-8") as source:
                cached = json.load(source)

            replay_client = _RecordedClient(_price_payload("WRONG"))
            replayed = build_twelve_data_market_rows(
                self.bundle,
                {"AMAT": _companyfacts()},
                replay_client,
                as_of=date(2026, 9, 26),
                retrieved_on=date(2026, 9, 27),
                raw_cache=RawResponseCache(StorageLayout(root)),
            )

        self.assertEqual(client.calls[0][0], "AMAT")
        self.assertEqual(replay_client.calls, [])
        self.assertEqual(replayed, rows)
        self.assertEqual(rows[0]["price_date"], "2026-09-25")
        self.assertEqual(rows[0]["close"], "10.75")
        self.assertEqual(rows[0]["shares_outstanding"], "12345678")
        self.assertEqual(rows[0]["adjustment"], "unadjusted")
        self.assertNotIn("apikey", cached["request_url"])
        self.assertEqual(imported.prices[0].share_source_id, f"sec:{ACCESSION}")
        preserved = next(s for s in imported.sources if s.source_id == f"sec:{ACCESSION}")
        self.assertEqual(preserved.accession, ACCESSION)

    def test_reviewed_multiclass_count_requires_its_exact_saved_filing(self):
        company = Company(
            security_id="cik:0001562088",
            ticker="DUOL",
            name="Duolingo, Inc.",
            currency="USD",
            business_type="operating",
            classification_reason="Recorded adapter fixture.",
            classified_at=date(2026, 9, 20),
        )
        anchor = {
            "cik": 1562088,
            "facts": {"us-gaap": {"Assets": {"units": {"USD": [{
                "end": "2026-06-30",
                "val": 1,
                "accn": "0001628280-26-053603",
                "form": "10-Q",
                "filed": "2026-08-06",
            }]}}}},
        }
        selected = select_sec_outstanding_shares(
            company,
            anchor,
            price_date=date(2026, 9, 25),
            available_on=date(2026, 9, 26),
            sources={},
            retrieved_on=date(2026, 9, 27),
        )
        self.assertEqual(selected.value, 46_786_269)
        self.assertEqual(selected.share_count_date, date(2026, 8, 4))
        self.assertIn("Class A plus", selected.source_concept)

        anchor["facts"] = {}
        with self.assertRaisesRegex(ValueError, "no usable SEC"):
            select_sec_outstanding_shares(
                company,
                anchor,
                price_date=date(2026, 9, 25),
                available_on=date(2026, 9, 26),
                sources={},
                retrieved_on=date(2026, 9, 27),
            )

    def test_diluted_weighted_average_shares_are_not_a_fallback(self):
        payload = {
            "cik": 123,
            "facts": {"us-gaap": {
                "WeightedAverageNumberOfDilutedSharesOutstanding": {
                    "units": {"shares": [{
                        "start": "2026-01-01",
                        "end": "2026-06-30",
                        "val": 99_000_000,
                        "accn": ACCESSION,
                        "form": "10-Q",
                        "filed": "2026-08-15",
                    }]}
                }
            }},
        }
        with self.assertRaisesRegex(ValueError, "no usable SEC"):
            select_sec_outstanding_shares(
                self.company,
                payload,
                price_date=date(2026, 9, 25),
                available_on=date(2026, 9, 26),
                sources={self.sec_source.source_id: self.sec_source},
                retrieved_on=date(2026, 9, 27),
            )

    def test_rejects_wrong_instrument_metadata_before_writing_a_row(self):
        payload = _price_payload("OTHER")
        with self.assertRaisesRegex(TwelveDataError, "expected AMAT"):
            build_twelve_data_market_rows(
                self.bundle,
                {"AMAT": _companyfacts()},
                _RecordedClient(payload),
                as_of=date(2026, 9, 26),
                retrieved_on=date(2026, 9, 27),
            )

    def test_uses_reviewed_exchange_qualified_symbol(self):
        tpc = Company(
            security_id=self.company.security_id,
            ticker="TPC",
            name="Tutor Perini Corporation",
            currency="USD",
            business_type="operating",
            classification_reason="Recorded adapter fixture.",
            classified_at=date(2026, 9, 20),
        )
        client = _RecordedClient(_price_payload("TPC", exchange="NYSE", mic_code="XNYS"))
        build_twelve_data_market_rows(
            ResearchBundle(
                companies=(tpc,),
                sources=(self.sec_source,),
                facts=(),
                prices=(),
            ),
            {"TPC": _companyfacts()},
            client,
            as_of=date(2026, 9, 26),
            retrieved_on=date(2026, 9, 27),
        )
        self.assertEqual(client.calls[0][0], "TPC:NYSE")

    def test_accepts_reviewed_reit_type_and_rejects_zero_volume_close(self):
        abr = Company(
            security_id=self.company.security_id,
            ticker="ABR",
            name="Arbor Realty Trust, Inc.",
            currency="USD",
            business_type="reit",
            classification_reason="Recorded adapter fixture.",
            classified_at=date(2026, 9, 20),
        )
        bundle = ResearchBundle(
            companies=(abr,), sources=(self.sec_source,), facts=(), prices=()
        )
        payload = _price_payload(
            "ABR", exchange="NYSE", mic_code="XNYS", instrument_type="REIT"
        )
        rows = build_twelve_data_market_rows(
            bundle,
            {"ABR": _companyfacts()},
            _RecordedClient(payload),
            as_of=date(2026, 9, 26),
            retrieved_on=date(2026, 9, 27),
        )
        self.assertEqual(rows[0]["ticker"], "ABR")

        payload["values"][0]["volume"] = "0"
        with self.assertRaisesRegex(TwelveDataError, "zero volume"):
            build_twelve_data_market_rows(
                bundle,
                {"ABR": _companyfacts()},
                _RecordedClient(payload),
                as_of=date(2026, 9, 26),
                retrieved_on=date(2026, 9, 27),
            )


def _companyfacts():
    return {
        "cik": 123,
        "facts": {"dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {"shares": [{
                    "end": "2026-08-10",
                    "val": 12_345_678,
                    "accn": ACCESSION,
                    "form": "10-Q",
                    "filed": "2026-08-15",
                }]}
            }
        }},
    }


def _price_payload(symbol, *, exchange="NASDAQ", mic_code="XNGS", instrument_type="Common Stock"):
    return {
        "meta": {
            "symbol": symbol,
            "currency": "USD",
            "exchange": exchange,
            "mic_code": mic_code,
            "type": instrument_type,
        },
        "values": [
            {"datetime": "2026-09-25", "close": "10.75", "volume": "200"},
            {"datetime": "2026-09-24", "close": "10.25", "volume": "100"},
        ],
        "status": "ok",
    }


if __name__ == "__main__":
    unittest.main()
