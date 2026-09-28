# SEC annual research run: 30 Development companies

Date and evaluation cutoff: September 20, 2026. This extends the
[two-company pilot](sec-annual-pilot.md); the 60-company held-out Evaluation
set was neither imported nor assessed.

The workbook's 30 Development tickers were matched to SEC CIKs by exact ticker
and exchange. Their saved SEC Company Facts responses produced a replayable
bundle of **30 companies, 3,435 annual facts, and 173 filing sources**. The
[company reports](../research_runs/sec-development-2026-09-20/README.md) and
[comparison table](../research_runs/sec-development-2026-09-20/comparison.csv)
show each feature's availability and research queue. Those generated files and
the raw/normalized data are ignored by Git; the commands below regenerate
them from locally saved SEC responses.

| Provisional routing | Companies | Treatment in this run |
|---|---:|---|
| Established operating business | 11 | Current annual quality, growth, and resilience checks run; each has missing evidence. |
| Bank, REIT, utility, specialty finance, or cyclical business | 17 | Annual facts remain visible; operating-business judgments are withheld for a specialized or through-cycle framework. |
| Operating business needing maturity/coverage review | 2 | Annual facts remain visible; established-business judgments are withheld. |

All 30 appear in `evidence_needed`. Twenty-nine have six annual period ends;
AMTM has four. All 30 have incomplete latest-year feature coverage, so none
has a complete valuation, investment ranking, or investment recommendation.
There is no dated price/share-count import, analyst thesis, or bear/base/bull
scenario in this bundle. The existing Magic Formula and Piotroski screens have
not been run on these companies.

## Concept and routing decisions

`src/stocks_infer/research/sec_companyfacts.py` records the provisional total
revenue tag for each Development company. Similar SEC concepts may be
components rather than totals: ANDE's 2025 `Revenues` is about $11.0 billion,
while its `RevenueFromContractWithCustomerExcludingAssessedTax` is about $1.5
billion; PECO's corresponding values are about $727 million and $13 million.
The run chooses the total where present and leaves ABR and NAVI revenue
unavailable rather than substituting an unrelated income item. Other standard
US-GAAP concepts are imported when present. A combined long- and short-term
debt concept is used only when SEC supplies it; standalone long-term debt is
not mislabeled total debt. Negative SEC interest-expense observations are
withheld pending review, without changing their signs.

The routing is based on the workbook's line of business and remains provisional.
COF and FHN are banks; VTR, EPR, ABR, and PECO are REITs; CMS is a utility;
NAVI is specialty finance. CAT, COHR, BWA, M, OC, ANDE, SEI, TPC, and ROAD
are marked cyclical for through-cycle review. DUOL and NEO reach
`needs_review` under the existing profitability-history rule. Company reports
record the routing reason and missing metrics; a poor or absent metric alone
does not exclude a company.

These are first-pass Company Facts mappings, **not a completed filing-by-filing
reconciliation**. SEC Company Facts covers standardized entity-wide tags;
company-specific disclosures, debt definitions, acquisition effects, unusual
periods, and segment context still need review. In particular, AMTM's short
history, COHR's missing latest mapped operating-income fact, and finance/REIT
revenue definitions must be resolved before comparing those businesses with
peers. The fixed assessment thresholds are research prompts, not calibrated
investment signals.

## Reproduce the run

Keep the workbook at `company_universe/growth-value-company-universe.xlsx`.
Keep the official SEC ticker file at
`data/raw/sec-pilot/company_tickers_exchange.json` and one official SEC
Company Facts response per Development ticker at
`data/raw/sec-pilot/TICKER-companyfacts.json`. The URL pattern is
`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, using each
exact matched CIK. Follow the [SEC access guidelines](https://www.sec.gov/about/developer-resources)
and provide an identified User-Agent when downloading. Preserve the downloaded
responses for exact replay; later SEC refreshes may include revisions.

```bash
poetry run stocks-infer import-sec-development \
  --universe company_universe/growth-value-company-universe.xlsx \
  --ticker-map data/raw/sec-pilot/company_tickers_exchange.json \
  --company-facts-dir data/raw/sec-pilot \
  --as-of 2026-09-20 --retrieved-on 2026-09-20 \
  --output data/normalized/sec-development-2026-09-20.json

poetry run stocks-infer research \
  --input data/normalized/sec-development-2026-09-20.json \
  --as-of 2026-09-20 --run-id sec-development-2026-09-20
```

Both commands refuse to overwrite existing output. Use a fresh output path and
run ID for a new retrieval. The next meaningful release gate is to reconcile
the provisional mappings and framework routing against the companies' 10-Ks,
then add quarterly normalization and sourced market observations before any
valuation comparison. Freeze those rules before opening the Evaluation set.

The first [filing reconciliation and narrative pass](sec-development-reconciliation.md)
now resolves debt for the 11 operating-framework companies and records the
material accounting and business-context exceptions found in their filings.
