# Dated market-data CSV import

Contract version: `dated-market-csv/0.1.0`

This release adds sourced closing prices and outstanding-share counts to an
existing research bundle. It is a strict recorded-data boundary: it does not
download prices, infer missing fields, convert currencies, or silently accept an
adjusted price series.

## Why price and shares have separate sources

A closing price commonly comes from an exchange or market-data vendor, while the
latest outstanding-share count comes from a dated filing. Each imported row
therefore preserves a price source and a share-count source. They may be the same
document, but the CSV must say so explicitly by leaving all `share_source_*`
fields blank.

The valuation share count must be on the same split basis as the unadjusted
closing price. The importer rejects adjusted prices and validates the dates, but
it cannot prove the supplied share basis independently. Use a post-split share
observation when possible; otherwise reconcile the transformation outside the
importer and retain its source evidence.

## CSV schema

The CSV requires exactly these columns. Column order does not matter.

| Column | Meaning |
|---|---|
| `ticker` | Ticker in the input research bundle; matching is case-insensitive |
| `price_date` | Trading date of the closing price |
| `available_at` | First date the combined price/share observation was usable |
| `close` | Positive, finite, unadjusted closing price |
| `currency` | Must equal the company's bundle currency; no implicit conversion |
| `adjustment` | Must be `unadjusted` |
| `shares_outstanding` | Positive absolute shares, not thousands or millions |
| `share_count_date` | Effective date of the outstanding-share count; cannot follow `price_date` |
| `price_source_id` | Stable identifier for the price source |
| `price_source_title` | Human-readable price-source title |
| `price_source_url` | HTTPS URL for the price evidence |
| `price_source_published_at` | Publication date of the price evidence |
| `price_source_retrieved_at` | Retrieval date, on or after publication |
| `share_source_id` | Stable share-source identifier; blank means use the price source |
| `share_source_title` | Required when `share_source_id` is supplied |
| `share_source_url` | Required HTTPS URL when `share_source_id` is supplied |
| `share_source_published_at` | Required when `share_source_id` is supplied |
| `share_source_retrieved_at` | Required when `share_source_id` is supplied |

Example header and row:

```csv
ticker,price_date,available_at,close,currency,adjustment,shares_outstanding,share_count_date,price_source_id,price_source_title,price_source_url,price_source_published_at,price_source_retrieved_at,share_source_id,share_source_title,share_source_url,share_source_published_at,share_source_retrieved_at
EXAMPLE,2026-09-25,2026-09-25,42.50,USD,unadjusted,100000000,2026-09-20,market:example-2026-09-25,Official closing price,https://example.com/price,2026-09-25,2026-09-26,filing:example-shares,Quarterly filing share count,https://example.com/filing,2026-09-20,2026-09-26
```

## Import and review

The command creates a new bundle and never overwrites an existing file:

```bash
poetry run stocks-infer import-market-csv \
  --input data/normalized/sec-development-quarterly-ttm-2026-09-20.json \
  --market-csv data/market/development-market-2026-09-25.csv \
  --output data/normalized/sec-development-market-2026-09-25.json \
  --require-all
```

`--require-all` requires at least one CSV row for every company in the input
bundle. Without it, a partial import is allowed and companies without market data
remain visible with an evidence warning.

Run research at the intended cutoff after importing:

```bash
poetry run stocks-infer research \
  --input data/normalized/sec-development-market-2026-09-25.json \
  --as-of 2026-09-25 --output-root . \
  --run-id sec-development-market-2026-09-25
```

At a cutoff, the workflow selects the latest price date whose observation was
available by that date. Different values with the same latest price and
availability dates create a conflict and withhold valuation. A price older than
seven days or a share count more than 180 days older than the price is stale and
cannot enter a price-opportunity research list.

Raw market CSVs, enriched bundles, and generated reports live beneath gitignored
`data/` and `research_runs/` directories. The repository contains the contract,
importer, and synthetic validation without publishing licensed market data.

## Provider selection boundary

This importer remains provider-neutral. Provider adapters emit this same
contract, so changing a provider does not change downstream valuation logic.
Historical coverage, correction behavior, corporate-action handling, rate limits,
and redistribution terms still require separate review for each provider.

## Twelve Data coverage trial

Twelve Data requires a personal API key for non-demo symbols. Keep the key out of
the repository and provide it through the process environment or the gitignored
local `.env` file:

```dotenv
TWELVE_DATA_API_KEY=paste-key-here
```

Then run:

```bash
poetry run stocks-infer probe-twelve-data \
  --input data/normalized/sec-development-quarterly-ttm-2026-09-20.json \
  --start-date 2007-01-01 --end-date 2026-09-26 \
  --output data/market/twelve-data-development-coverage.csv
```

The command requests `1day` observations with `adjust=none`, throttles to eight
requests per minute by default, and writes one row per company plus a sibling
summary JSON file. It verifies exact symbol and currency metadata, positive and
unique closing prices, requested date bounds, recent coverage, and the amount of
history returned. It also flags missing or persistently zero volume and long runs
of unchanged closes, which can reveal non-traded pre-listing records. API
authentication uses a request header, so neither report contains the key. If a
bare ticker is ambiguous across countries, the probe uses
the symbol-search endpoint to retry the primary US listing with an
exchange-qualified symbol and records that mapping as a warning for review.

The free Basic plan exposes the time-series endpoint, but the dedicated split
and dividend endpoints are part of a paid fundamentals plan. The raw-price
parameter can be checked across known corporate actions by comparing
`adjust=none` with `adjust=splits`; outstanding-share evidence continues to come
from dated SEC filings.

## Twelve Data plus SEC adapter

Adapter version: `twelve-data-sec-market/0.1.0`

The adapter builds the strict CSV directly from two sources:

- the latest Twelve Data `1day`, `adjust=none` close on or before the cutoff;
- the latest SEC cover-page outstanding-share count whose effective and filing
  dates are both usable at that cutoff.

It validates the returned symbol, exchange, MIC, USD currency, reviewed
common-stock or REIT instrument type, positive close, positive latest-day
trading volume, SEC CIK, whole positive share count, and source dates before it
writes the CSV. It never substitutes weighted-average diluted EPS shares for
outstanding shares. For the Development cohort, 26 companies use
`dei:EntityCommonStockSharesOutstanding`. COKE, DUOL, ROAD, and SEI use reviewed
multi-class totals tied to exact 2026 10-Q accessions; the adapter admits those
totals only when the saved Company Facts payload proves that filing is present.
TPC uses the coverage-trial mapping `TPC:NYSE`.

The four reviewed totals come from the cover pages of the
[COKE 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/317540/000162828026053370/coke-20260703.htm),
[DUOL 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1562088/000162828026053603/duol-20260630.htm),
[ROAD 2026 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/1718227/000162828026054661/road-20260630.htm), and
[SEI 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1697500/000162828026054349/sei-20260630.htm).

Build a Development-cohort snapshot:

```bash
poetry run stocks-infer build-twelve-data-market \
  --input data/normalized/sec-development-quarterly-ttm-2026-09-20.json \
  --company-facts-dir data/raw/sec-pilot \
  --as-of 2026-09-26 --retrieved-on 2026-09-27 \
  --output data/market/twelve-data-sec-development-2026-09-26.csv
```

The command refuses to replace an existing CSV and waits for the entire cohort
to succeed before writing it. Each credential-free response is cached under
`data/raw/<retrieval-date>/twelve-data/` and is reused when the same dated command
is resumed; the API key remains only in the request header. Tests use recorded
response objects and consume no provider credits.

Import the resulting CSV with `import-market-csv --require-all`, then run the
research command at the price cutoff. A future filing that continues to omit a
usable non-dimensional cover-page fact requires another reviewed, accession-
locked multi-class entry rather than an inferred fallback.
