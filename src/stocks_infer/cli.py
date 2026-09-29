"""Command-line interface for deterministic screening runs."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Sequence

from stocks_infer.algorithms import registry
from stocks_infer.config import AppConfig
from stocks_infer.dataset import fingerprint_screening_records
from stocks_infer.models import RunManifest
from stocks_infer.recorded_data import load_screening_records
from stocks_infer.runner import ScreeningRunner
from stocks_infer.storage import ParquetSnapshotStore, RunArtifactStore, StorageLayout


def build_parser(config: AppConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stocks-infer",
        description="Run reproducible, explainable stock screens.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser(
        "list-algorithms", help="List registered screening algorithms."
    )

    research = commands.add_parser("research", help="Create dated company research reports from a recorded historical bundle.")
    research.add_argument("--input", type=Path, required=True)
    research.add_argument("--as-of", type=date.fromisoformat, required=True)
    research.add_argument("--output-root", type=Path, default=config.output_root)
    research.add_argument("--run-id")
    compare = commands.add_parser("research-compare", help="Compare two saved research reviews and verify their artifacts.")
    compare.add_argument("--before", type=Path, required=True)
    compare.add_argument("--after", type=Path, required=True)

    market = commands.add_parser("import-market-csv", help="Add sourced, dated market observations to a research bundle.")
    market.add_argument("--input", type=Path, required=True, help="Existing research bundle JSON.")
    market.add_argument("--market-csv", type=Path, required=True, help="Strict market-observation CSV.")
    market.add_argument("--output", type=Path, required=True, help="New bundle JSON; existing files are never overwritten.")
    market.add_argument("--require-all", action="store_true", help="Require at least one imported row for every company in the bundle.")

    twelve_data = commands.add_parser(
        "probe-twelve-data",
        help="Test Twelve Data daily-price coverage for every company in a research bundle.",
    )
    twelve_data.add_argument("--input", type=Path, required=True, help="Existing research bundle JSON.")
    twelve_data.add_argument("--output", type=Path, required=True, help="New coverage-report CSV.")
    twelve_data.add_argument("--start-date", type=date.fromisoformat, default=date(2007, 1, 1))
    twelve_data.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    twelve_data.add_argument(
        "--requests-per-minute",
        type=int,
        default=8,
        help="Throttle to the account plan; Twelve Data Basic currently allows 8.",
    )

    twelve_market = commands.add_parser(
        "build-twelve-data-market",
        help="Build a strict market CSV from Twelve Data closes and SEC shares.",
    )
    twelve_market.add_argument("--input", type=Path, required=True, help="Existing SEC-normalized research bundle JSON.")
    twelve_market.add_argument("--company-facts-dir", type=Path, required=True, help="Directory containing TICKER-companyfacts.json files.")
    twelve_market.add_argument("--output", type=Path, required=True, help="New strict market-observation CSV.")
    twelve_market.add_argument("--as-of", type=date.fromisoformat, required=True, help="Latest date prices and filings may use.")
    twelve_market.add_argument("--retrieved-on", type=date.fromisoformat, default=date.today())
    twelve_market.add_argument("--raw-root", type=Path, default=Path("."), help="Root beneath which data/raw stores credential-free responses.")
    twelve_market.add_argument("--lookback-days", type=int, default=14)
    twelve_market.add_argument(
        "--requests-per-minute",
        type=int,
        default=8,
        help="Throttle to the account plan; Twelve Data Basic currently allows 8.",
    )

    sec_pilot = commands.add_parser("import-sec-pilot", help="Normalize reviewed SEC annual and quarterly concepts for development and difficult cases.")
    sec_pilot.add_argument("--universe", type=Path, required=True)
    sec_pilot.add_argument("--ticker-map", type=Path, required=True)
    sec_pilot.add_argument("--company-facts", action="append", required=True, metavar="TICKER=PATH")
    sec_pilot.add_argument("--as-of", type=date.fromisoformat, required=True)
    sec_pilot.add_argument("--retrieved-on", type=date.fromisoformat, default=date.today())
    sec_pilot.add_argument("--output", type=Path, required=True)

    development = commands.add_parser("import-sec-development", help="Normalize all 30 Development companies from saved SEC Company Facts.")
    development.add_argument("--universe", type=Path, required=True)
    development.add_argument("--ticker-map", type=Path, required=True)
    development.add_argument("--company-facts-dir", type=Path, required=True)
    development.add_argument("--as-of", type=date.fromisoformat, required=True)
    development.add_argument("--retrieved-on", type=date.fromisoformat, default=date.today())
    development.add_argument("--output", type=Path, required=True)

    fixture = commands.add_parser(
        "screen-fixture",
        help="Run algorithms against a recorded canonical JSON dataset.",
    )
    fixture.add_argument("--input", type=Path, required=True)
    fixture.add_argument(
        "--output-root", type=Path, default=config.output_root
    )
    fixture.add_argument(
        "--shortlist-size", type=int, default=config.shortlist_size
    )
    fixture.add_argument(
        "--minimum-algorithms",
        type=int,
        help="Minimum successful algorithm scores required for consensus; defaults to all.",
    )
    fixture.add_argument(
        "--algorithm",
        action="append",
        choices=registry.names(),
        help="Algorithm to run; repeat the option to select several. Defaults to all.",
    )
    fixture.add_argument(
        "--run-id",
        help="Stable run identifier. A timestamped identifier is generated by default.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    config = AppConfig.from_environment()
    parser = build_parser(config)
    arguments = parser.parse_args(argv)

    if arguments.command == "list-algorithms":
        for algorithm in registry.all():
            print(f"{algorithm.slug} {algorithm.version} - {algorithm.description}")
        return 0

    if arguments.command == "screen-fixture":
        return _screen_fixture(arguments)

    if arguments.command == "research":
        from stocks_infer.research.artifacts import write_research_run

        destination = write_research_run(arguments.input, arguments.output_root, arguments.as_of, arguments.run_id)
        print(f"Research review: {destination / 'README.md'}")
        print(f"Comparison: {destination / 'comparison.csv'}")
        return 0

    if arguments.command == "research-compare":
        from stocks_infer.research.artifacts import compare_runs

        print(json.dumps(compare_runs(arguments.before, arguments.after), indent=2))
        return 0

    if arguments.command == "import-market-csv":
        from stocks_infer.research.io import load_bundle, write_json
        from stocks_infer.research.market_csv import import_market_csv

        if arguments.output.exists():
            raise FileExistsError(f"market-enriched bundle already exists: {arguments.output}")
        bundle = import_market_csv(
            load_bundle(arguments.input),
            arguments.market_csv,
            require_all=arguments.require_all,
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(arguments.output, bundle)
        covered = len({price.security_id for price in bundle.prices})
        print(
            f"Bundle now contains {len(bundle.prices)} market observations covering "
            f"{covered}/{len(bundle.companies)} companies: {arguments.output}"
        )
        return 0

    if arguments.command == "probe-twelve-data":
        from stocks_infer.research.io import load_bundle
        from stocks_infer.research.twelve_data import (
            TWELVE_DATA_API_KEY_ENV,
            TwelveDataClient,
            load_twelve_data_api_key,
            probe_twelve_data_coverage,
            write_twelve_data_coverage,
        )

        api_key = load_twelve_data_api_key()
        if not api_key:
            raise ValueError(
                f"set {TWELVE_DATA_API_KEY_ENV} to a personal Twelve Data API key"
            )
        if arguments.output.exists() or arguments.output.with_suffix(".summary.json").exists():
            raise FileExistsError(f"Twelve Data coverage output already exists: {arguments.output}")
        results = probe_twelve_data_coverage(
            load_bundle(arguments.input),
            TwelveDataClient(
                api_key,
                requests_per_minute=arguments.requests_per_minute,
            ),
            start_date=arguments.start_date,
            end_date=arguments.end_date,
            on_result=lambda index, total, result: print(
                f"[{index}/{total}] {result.ticker}: {result.status}"
                + (f" ({result.issues})" if result.issues else "")
            ),
        )
        summary_path = write_twelve_data_coverage(
            arguments.output, results, retrieved_at=date.today()
        )
        counts = {
            status: sum(result.status == status for result in results)
            for status in ("covered", "warning", "error")
        }
        print(f"Coverage report: {arguments.output}")
        print(f"Coverage summary: {summary_path}")
        print(
            f"Results: {counts['covered']} covered, {counts['warning']} warnings, "
            f"{counts['error']} errors"
        )
        return 0

    if arguments.command == "build-twelve-data-market":
        from stocks_infer.research.io import load_bundle
        from stocks_infer.research.twelve_data import (
            TWELVE_DATA_API_KEY_ENV,
            TwelveDataClient,
            load_twelve_data_api_key,
        )
        from stocks_infer.research.twelve_data_adapter import (
            build_twelve_data_market_rows,
            load_companyfacts_directory,
            write_twelve_data_market_csv,
        )
        from stocks_infer.storage import RawResponseCache, StorageLayout

        if arguments.output.exists():
            raise FileExistsError(
                f"Twelve Data market CSV already exists: {arguments.output}"
            )
        api_key = load_twelve_data_api_key()
        if not api_key:
            raise ValueError(
                f"set {TWELVE_DATA_API_KEY_ENV} to a personal Twelve Data API key"
            )
        bundle = load_bundle(arguments.input)
        payloads = load_companyfacts_directory(
            arguments.company_facts_dir, bundle.companies
        )
        rows = build_twelve_data_market_rows(
            bundle,
            payloads,
            TwelveDataClient(
                api_key,
                requests_per_minute=arguments.requests_per_minute,
            ),
            as_of=arguments.as_of,
            retrieved_on=arguments.retrieved_on,
            raw_cache=RawResponseCache(StorageLayout(arguments.raw_root)),
            lookback_days=arguments.lookback_days,
            on_result=lambda index, total, ticker, price_date: print(
                f"[{index}/{total}] {ticker}: {price_date.isoformat()}"
            ),
        )
        write_twelve_data_market_csv(arguments.output, rows)
        print(
            f"Market CSV: {arguments.output} ({len(rows)} companies; "
            "Twelve Data prices plus SEC outstanding shares)"
        )
        return 0

    if arguments.command == "import-sec-pilot":
        from stocks_infer.research.io import write_json
        from stocks_infer.research.sec_companyfacts import companyfacts_bundle, load_sec_payloads
        from stocks_infer.research.universe import load_universe, match_sec_identifiers

        if arguments.output.exists():
            raise FileExistsError(f"normalized bundle already exists: {arguments.output}")
        universe = load_universe(arguments.universe)
        payloads = load_sec_payloads(arguments.company_facts)
        ticker_map = json.loads(arguments.ticker_map.read_text(encoding="utf-8"))
        identifiers = match_sec_identifiers(
            tuple(company for company in universe if company.ticker in payloads), ticker_map
        )
        bundle = companyfacts_bundle(
            universe, identifiers, payloads,
            as_of=arguments.as_of, retrieved_on=arguments.retrieved_on,
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(arguments.output, bundle)
        print(f"Normalized {len(bundle.companies)} companies and {len(bundle.facts)} SEC facts: {arguments.output}")
        return 0

    if arguments.command == "import-sec-development":
        from stocks_infer.research.io import write_json
        from stocks_infer.research.sec_companyfacts import companyfacts_bundle
        from stocks_infer.research.universe import load_universe, match_sec_identifiers

        if arguments.output.exists():
            raise FileExistsError(f"normalized bundle already exists: {arguments.output}")
        development_companies = tuple(
            company for company in load_universe(arguments.universe)
            if company.test_set == "Development"
        )
        ticker_map = json.loads(arguments.ticker_map.read_text(encoding="utf-8"))
        identifiers = match_sec_identifiers(development_companies, ticker_map)
        payloads = {
            company.ticker: json.loads((arguments.company_facts_dir / f"{company.ticker}-companyfacts.json").read_text(encoding="utf-8"))
            for company in development_companies
        }
        bundle = companyfacts_bundle(
            development_companies, identifiers, payloads,
            as_of=arguments.as_of, retrieved_on=arguments.retrieved_on,
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(arguments.output, bundle)
        print(f"Normalized {len(bundle.companies)} Development companies and {len(bundle.facts)} SEC facts: {arguments.output}")
        return 0

    parser.error(f"unknown command: {arguments.command}")
    return 2


def _screen_fixture(arguments: argparse.Namespace) -> int:
    records = load_screening_records(arguments.input)
    as_of_dates = {record.as_of_date for record in records}
    if len(as_of_dates) != 1:
        raise ValueError("all fixture records must have the same as-of date")
    as_of_date = as_of_dates.pop()

    algorithms = registry.select(arguments.algorithm)
    minimum_algorithms = arguments.minimum_algorithms or len(algorithms)
    parameters = {
        "shortlist_size": arguments.shortlist_size,
        "minimum_algorithms": minimum_algorithms,
    }
    runner = ScreeningRunner(algorithms)
    result = runner.run(
        records,
        as_of_date=as_of_date,
        shortlist_size=arguments.shortlist_size,
        minimum_algorithms=minimum_algorithms,
        parameters=parameters,
    )

    started_at = datetime.now(timezone.utc)
    run_id = arguments.run_id or (
        f"{as_of_date.isoformat()}-{started_at.strftime('%Y%m%dT%H%M%S%fZ')}"
    )
    layout = StorageLayout(arguments.output_root)
    parquet = ParquetSnapshotStore()
    dataset_fingerprint = fingerprint_screening_records(records)
    normalized_path = (
        layout.normalized_directory(as_of_date)
        / dataset_fingerprint
        / "screening_records.parquet"
    )
    if not normalized_path.exists():
        parquet.write_screening_records(normalized_path, records)

    sources = tuple(
        sorted(
            {
                source
                for record in records
                for source in (record.fundamentals_source, record.price_source)
            }
        )
    )
    manifest = RunManifest(
        schema_version=1,
        run_id=run_id,
        started_at=started_at,
        as_of_date=as_of_date,
        universe=f"recorded-fixture:{arguments.input.name}",
        dataset_fingerprint=dataset_fingerprint,
        input_snapshot=str(normalized_path.relative_to(arguments.output_root)),
        data_sources=sources,
        algorithms=tuple(
            {"slug": algorithm.slug, "version": algorithm.version}
            for algorithm in algorithms
        ),
        parameters=parameters,
        evaluated_count=len(records),
        shortlisted_count=len(result.shortlist),
    )
    artifact_store = RunArtifactStore(layout, parquet)
    run_directory = artifact_store.write(
        manifest=manifest,
        all_scores=result.algorithm_scores + result.consensus_scores,
        shortlist=result.shortlist,
    )

    print(f"Normalized snapshot: {normalized_path}")
    print(f"Run artifacts: {run_directory}")
    print("Shortlist:")
    for score in result.shortlist:
        print(f"  {score.rank:>3}  {score.ticker:<8} {score.score:>7.2f}")
    return 0
