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

## Research workflow (first implementation milestone)

The recorded-data research workflow adds historical fact provenance, separate
quality/growth/resilience/evidence assessments, dated thesis claims, and
researcher-supplied valuation scenarios. Companies remain visible when evidence
is missing or another framework is needed. There is no universal company rank.

Run the **synthetic ten-company example** (these are invented businesses and
financials, not investment candidates):

```bash
poetry run stocks-infer research \
  --input tests/fixtures/research_watchlist.json \
  --as-of 2026-09-18 \
  --output-root . \
  --run-id my-first-research
```

Open `research_runs/my-first-research/README.md` for the company reports. The directory also
contains `comparison.csv`, `research.json`, the replayable `input.json`,
`facts.parquet`, `features.parquet`, and a versioned, fingerprinted manifest.
Existing runs cannot be overwritten; choose a new run ID when repeating a review.

To replay a saved input or compare two reviews:

```bash
poetry run stocks-infer research \
  --input research_runs/my-first-research/input.json \
  --as-of 2026-09-18 --run-id my-replay
poetry run stocks-infer research-compare \
  --before research_runs/my-first-research --after research_runs/my-replay
```

The comparison verifies artifact hashes before reporting changed evidence,
market observations, thesis, valuation, or research-list membership.

This milestone uses annual normalized JSON inputs. SEC ingestion, quarterly
normalization, market CSV import, and reconciliation against a real watchlist
remain release work. Assessment thresholds are explicit research heuristics,
not validated investment signals. See the
[implementation plan](docs/research-workflow-implementation-plan.md) and
[framework contract and limitations](docs/established-business-research-contract.md).
