# First SEC Annual-Facts Pilot

Date: September 20, 2026  
Status: two-company annual-data pilot; no market-price import, quarterly TTM,
thesis, or valuation scenarios yet.

## Universe and evaluation boundary

Source workbook: `company_universe/growth-value-company-universe.xlsx`, SHA-256
`7ca01721d9ee47d83ac26560e284cd1f1109b43cd52ce93abc36b853fe085d79`.
The Companies worksheet has 100 distinct tickers: 30 Development, 60
Evaluation, and 10 Difficult case. All 100 matched one SEC ticker/CIK and the
listed exchange in the SEC ticker file downloaded on September 20, 2026.
The workbook's style and size fields remain sampling labels, not screening
scores or financial classifications. The importer refuses Evaluation rows so
the held-out set cannot enter pilot tuning by accident.

| Pilot case | Workbook set | SEC CIK | Role |
|---|---|---|---|
| WSM, Williams-Sonoma | Development | 0000719955 | Established retailer with incomplete debt/interest concepts |
| AZO, AutoZone | Difficult case | 0000866787 | Tests negative book equity and capital-return interpretation |

The SEC ticker file and both Company Facts responses are retained locally under
`data/raw/sec-pilot/` (ignored by Git). They are not part of the repository.
The normalized, replayable 280-fact bundle is
`data/normalized/sec-pilot-2026-09-20.json` (also ignored by Git). The current
generated reports are under `research_runs/sec-pilot-final-2026-09-20/`.

## Source and formula checks

The importer maps only explicitly reviewed US-GAAP concepts in
`src/stocks_infer/research/sec_companyfacts.py`. It imports annual 10-K facts
available by the September 20 cutoff, keeps each filing accession and filing
date, and preserves comparative revisions. It does not fill missing concepts
with zero or assume a company has no debt merely because a debt tag is absent.

The latest imported amounts below are in **USD millions**. They match the
corresponding 10-K line items after multiplying the filing's thousands by
1,000:

| Metric | WSM FY ended Feb 1, 2026 | AZO FY ended Aug 30, 2025 |
|---|---:|---:|
| Revenue | 7,806.816 | 18,938.717 |
| Operating income | 1,415.722 | 3,610.156 |
| Operating cash flow | 1,314.889 | 3,117.337 |
| Capital expenditure | 259.438 | 1,327.257 |
| Book equity | 2,082.559 | (3,414.313) |

Sources: [WSM 2026 Form 10-K](https://www.sec.gov/Archives/edgar/data/719955/000071995526000059/wsm-20260201.htm),
[AZO 2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/866787/000110465925102611/azo-20250830x10k.htm).
These checks cover selected latest-year line items, not every imported period
or a full accounting reconciliation.

WSM has no current mapped debt or interest-expense facts in this pilot. Debt,
net debt, interest coverage, and the capital-return approximation stay
unavailable. AZO has negative book equity. Its pre-tax capital-return
approximation is marked `not_meaningful`, even where debt minus cash makes the
simple invested-capital denominator positive. Its other observed financial
facts remain visible. Both companies currently belong to `evidence_needed`
because no dated market price, thesis, or scenarios were supplied.
AZO's mapped debt is the filing's gross combined debt before discounts and
issuance costs; a later valuation bridge must decide how to reconcile that
amount to its balance-sheet carrying value and other claims.
Both companies' prior comparison years contained 53 weeks, so their latest
raw growth rates carry an unequal-period warning and are not week-adjusted.

## Reproduce locally

Download three public SEC JSON files to `data/raw/sec-pilot/` using an identified
User-Agent and the SEC's [access guidelines](https://www.sec.gov/about/developer-resources):

```text
https://www.sec.gov/files/company_tickers_exchange.json
https://data.sec.gov/api/xbrl/companyfacts/CIK0000719955.json
https://data.sec.gov/api/xbrl/companyfacts/CIK0000866787.json
```

Save them respectively as `company_tickers_exchange.json`,
`WSM-companyfacts.json`, and `AZO-companyfacts.json`. Then run:

```bash
poetry run stocks-infer import-sec-pilot \
  --universe company_universe/growth-value-company-universe.xlsx \
  --ticker-map data/raw/sec-pilot/company_tickers_exchange.json \
  --company-facts WSM=data/raw/sec-pilot/WSM-companyfacts.json \
  --company-facts AZO=data/raw/sec-pilot/AZO-companyfacts.json \
  --as-of 2026-09-20 --retrieved-on 2026-09-20 \
  --output data/normalized/sec-pilot-2026-09-20.json

poetry run stocks-infer research \
  --input data/normalized/sec-pilot-2026-09-20.json \
  --as-of 2026-09-20 --run-id sec-pilot-final-2026-09-20
```

These commands do not overwrite existing outputs. Use a new output path and
run ID when repeating the pilot. The retrieval date should reflect when the
source files were actually fetched. SEC source responses can change with new
filings; replay the saved normalized input to reproduce the original run.

## Next gates

1. Review SEC concept selection and all six annual periods for both companies,
   including debt definitions, restatements, and fiscal-period alignment.
2. Normalize quarterly and year-to-date facts so the evaluation date uses the
   latest available TTM period, especially for AZO.
3. Import a dated unadjusted price and matching share count from a sourced
   market-data file; then add a manually reviewed thesis and scenarios.
4. Convert complete historical features into the existing Magic Formula and
   Piotroski algorithm inputs where their metrics and eligibility rules fit.
5. Extend the importer to the Development cohort, then freeze reviewed rules
   before touching the 60 Evaluation companies. The [30-company annual run](sec-development-run.md)
   is the next step; its mappings still need filing reconciliation.

This pilot establishes a path from the workbook to actual annual company facts.
It does not establish the financial merit of WSM or AZO or validate investment
performance.
