"""Tests for the Twelve Data coverage boundary."""

from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stocks_infer.research.io import load_bundle
from stocks_infer.research.twelve_data import (
    TwelveDataClient,
    TwelveDataError,
    TWELVE_DATA_API_KEY_ENV,
    load_twelve_data_api_key,
    probe_twelve_data_coverage,
    write_twelve_data_coverage,
)


FIXTURE = Path(__file__).parent / "fixtures" / "research_watchlist.json"


class _RecordedClient:
    def __init__(self, payloads, resolutions=None):
        self.payloads = payloads
        self.resolutions = resolutions or {}
        self.calls = []

    def daily_time_series(self, ticker, start_date, end_date):
        self.calls.append((ticker, start_date, end_date))
        payload = self.payloads[ticker]
        if isinstance(payload, Exception):
            raise payload
        return payload, f"https://api.twelvedata.com/time_series?symbol={ticker}&adjust=none"

    def resolve_exchange_symbol(self, company):
        return self.resolutions.get(company.ticker)


class TwelveDataCoverageTests(unittest.TestCase):
    def setUp(self):
        original = load_bundle(FIXTURE)
        self.bundle = type(original)(
            schema_version=original.schema_version,
            companies=original.companies[:2],
            sources=original.sources,
            facts=tuple(
                fact for fact in original.facts
                if fact.security_id in {company.security_id for company in original.companies[:2]}
            ),
            prices=tuple(
                price for price in original.prices
                if price.security_id in {company.security_id for company in original.companies[:2]}
            ),
            theses=tuple(
                thesis for thesis in original.theses
                if thesis.security_id in {company.security_id for company in original.companies[:2]}
            ),
            scenarios=tuple(
                scenario for scenario in original.scenarios
                if scenario.security_id in {company.security_id for company in original.companies[:2]}
            ),
        )

    def test_probe_reports_metadata_history_and_one_symbol_error(self):
        first, second = self.bundle.companies
        client = _RecordedClient({
            first.ticker: _payload(first.ticker, first.currency),
            second.ticker: TwelveDataError("symbol unavailable on plan"),
        })
        results = probe_twelve_data_coverage(
            self.bundle,
            client,
            start_date=date(2020, 1, 1),
            end_date=date(2026, 9, 26),
        )

        by_ticker = {result.ticker: result for result in results}
        self.assertEqual(by_ticker[first.ticker].status, "warning")
        self.assertEqual(by_ticker[first.ticker].requested_adjustment, "none")
        self.assertEqual(by_ticker[first.ticker].observation_count, 2)
        self.assertIn("history begins after requested start", by_ticker[first.ticker].issues)
        self.assertEqual(by_ticker[second.ticker].status, "error")
        self.assertIn("symbol unavailable", by_ticker[second.ticker].issues)

    def test_report_writes_csv_and_summary_without_secret(self):
        company = self.bundle.companies[0]
        results = probe_twelve_data_coverage(
            self.bundle,
            _RecordedClient({
                item.ticker: _payload(item.ticker, item.currency)
                for item in self.bundle.companies
            }),
            start_date=date(2026, 9, 18),
            end_date=date(2026, 9, 26),
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "coverage.csv"
            summary_path = write_twelve_data_coverage(
                output, results, retrieved_at=date(2026, 9, 27)
            )
            text = output.read_text(encoding="utf-8")
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertIn(company.ticker, text)
            self.assertNotIn("secret", text)
            self.assertEqual(summary["company_count"], 2)
            with self.assertRaises(FileExistsError):
                write_twelve_data_coverage(
                    output, results, retrieved_at=date(2026, 9, 27)
                )

    def test_probe_retries_an_ambiguous_ticker_with_exchange(self):
        company = self.bundle.companies[0]
        qualified = f"{company.ticker}:NYSE"
        client = _RecordedClient(
            {
                company.ticker: TwelveDataError(
                    "No data is available on the specified dates."
                ),
                qualified: _payload(company.ticker, company.currency),
            },
            resolutions={company.ticker: qualified},
        )
        single_company = type(self.bundle)(
            schema_version=self.bundle.schema_version,
            companies=(company,),
            sources=self.bundle.sources,
            facts=tuple(
                fact for fact in self.bundle.facts
                if fact.security_id == company.security_id
            ),
            prices=tuple(
                price for price in self.bundle.prices
                if price.security_id == company.security_id
            ),
            theses=tuple(
                thesis for thesis in self.bundle.theses
                if thesis.security_id == company.security_id
            ),
            scenarios=tuple(
                scenario for scenario in self.bundle.scenarios
                if scenario.security_id == company.security_id
            ),
        )
        result = probe_twelve_data_coverage(
            single_company,
            client,
            start_date=date(2026, 9, 18),
            end_date=date(2026, 9, 26),
        )[0]
        self.assertEqual(result.status, "warning")
        self.assertIn(qualified, result.issues)
        self.assertEqual([call[0] for call in client.calls], [company.ticker, qualified])

    def test_probe_flags_zero_volume_and_flat_prelisting_rows(self):
        company = self.bundle.companies[0]
        payload = _payload(company.ticker, company.currency)
        payload["values"] = [
            {
                "datetime": f"2026-09-{day:02d}",
                "close": "5.75",
                "volume": "0",
            }
            for day in range(15, 25)
        ] + [{"datetime": "2026-09-25", "close": "10", "volume": "1000"}]
        result = probe_twelve_data_coverage(
            _single_company_bundle(self.bundle, company),
            _RecordedClient({company.ticker: payload}),
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 26),
        )[0]
        self.assertEqual(result.status, "warning")
        self.assertEqual(result.zero_volume_count, 10)
        self.assertEqual(result.longest_flat_close_run, 10)
        self.assertIn("zero-volume", result.issues)
        self.assertIn("unchanged for 10 observations", result.issues)

    def test_client_rejects_missing_key_and_invalid_rate(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            TwelveDataClient(" ")
        with self.assertRaisesRegex(ValueError, "positive"):
            TwelveDataClient("secret", requests_per_minute=0)

    def test_api_key_can_be_loaded_from_gitignored_env_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / ".env"
            env_file.write_text(
                "# local credential\nTWELVE_DATA_API_KEY='recorded-key'\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {TWELVE_DATA_API_KEY_ENV: ""}):
                self.assertEqual(load_twelve_data_api_key(env_file), "recorded-key")


def _payload(ticker, currency):
    return {
        "meta": {
            "symbol": ticker,
            "currency": currency,
            "exchange": "NASDAQ",
            "mic_code": "XNAS",
            "type": "Common Stock",
        },
        "values": [
            {"datetime": "2026-09-18", "close": "10.25", "volume": "100"},
            {"datetime": "2026-09-25", "close": "10.75", "volume": "200"},
        ],
        "status": "ok",
    }


def _single_company_bundle(bundle, company):
    return type(bundle)(
        schema_version=bundle.schema_version,
        companies=(company,),
        sources=bundle.sources,
        facts=tuple(
            fact for fact in bundle.facts if fact.security_id == company.security_id
        ),
        prices=tuple(
            price for price in bundle.prices if price.security_id == company.security_id
        ),
        theses=tuple(
            thesis for thesis in bundle.theses if thesis.security_id == company.security_id
        ),
        scenarios=tuple(
            scenario for scenario in bundle.scenarios
            if scenario.security_id == company.security_id
        ),
    )


if __name__ == "__main__":
    unittest.main()
