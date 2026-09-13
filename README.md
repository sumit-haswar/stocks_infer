# Stocks Infer

Stocks Infer is a provider-neutral, reproducible stock-screening pipeline. It is
being rebuilt to screen active NASDAQ and NYSE companies with multiple
explainable algorithms and produce a shortlist for manual, long-term investment
research.

The current implementation slice provides:

- Canonical security, fundamentals, price, and screening models
- Contracts for universe, fundamentals, and market-data providers
- A registry for independently versioned screening algorithms
- Magic Formula and Piotroski F-Score implementations
- Consensus ranking across algorithm results
- Raw JSON caching and DuckDB-backed Parquet snapshots
- Complete run manifests, score files, and CSV shortlists
- A fixture-driven CLI for deterministic local runs

The legacy Yahoo HTML scraper remains in the repository temporarily as a
reference, but the new package does not use it.

## Setup

```bash
poetry install
```

## Run the tests

```bash
poetry run python -m unittest discover -s tests -v
```

## List available algorithms

```bash
poetry run stocks-infer list-algorithms
```

## Run the recorded example

```bash
poetry run stocks-infer screen-fixture \
  --input tests/fixtures/screening_records.json \
  --output-root . \
  --shortlist-size 3
```

The command writes the normalized input snapshot beneath `data/normalized/` and
the reproducible run artifacts beneath `runs/`.

See [the application rework design](docs/application-rework-design.md) for the
product direction and architecture decisions.
