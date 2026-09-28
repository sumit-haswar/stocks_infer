# Development cohort: quarterly and TTM normalization

Cutoff: **2026-09-20**  
Formula version: `annual-ttm-features/0.3.0`

This release adds a point-in-time quarterly and trailing-twelve-month trend layer
to the same 30-company Development cohort used for annual normalization. The 60
held-out Evaluation companies remain untouched.

- Normalized input: `data/normalized/sec-development-quarterly-ttm-2026-09-20.json`
- Reports: `research_runs/sec-development-quarterly-ttm-2026-09-20/`
- Imported facts: 14,719
- Companies with at least one complete four-quarter anchor window: 30 of 30

The normalized bundle, raw SEC payloads, and generated reports are local,
gitignored artifacts. They are not part of the GitHub source tree. The results
below record the verified local run; reproducing it requires the corresponding
saved Company Facts payloads under `data/raw/sec-pilot/`.

TTM values are evidence for trend review. The established-business assessments
continue to use annual features in this release, so a recent quarter cannot
silently change the yardstick or override a full-year result.

## Normalization rules

The importer keeps annual, YTD, discrete-quarter, and instant balance-sheet facts
as separate period types.

1. A reported 60–110 day interval is a discrete quarter.
2. A reported 111–300 day 10-Q interval is YTD.
3. A missing discrete quarter may be derived by subtracting an earlier cumulative
   interval with the same fiscal start. Direct reported quarters from the same
   filing date take precedence.
4. Weighted-average diluted shares use day-weighted subtraction rather than
   subtracting averages directly.
5. A TTM window needs four contiguous fiscal quarters spanning 330–400 days.
6. Each flow is summed from those quarters when available. If one metric lacks a
   discrete quarter, that metric may use `annual + current YTD - prior comparable
   YTD`. Comparable YTD durations may differ by at most seven days to accommodate
   52/53-week calendars; unequal TTM lengths produce a warning.
7. TTM diluted shares are day-weighted. Balance-sheet metrics use the closing
   date; return on capital uses opening and closing balances.
8. Conflicts remain invalid, missing values remain missing, and incompatible line
   definitions are not combined.

Every derived quarter records the input fact IDs in `source_concept`. Every TTM
feature records all raw or derived input fact IDs. Filing availability dates are
applied before selection, so later filings cannot enter an earlier cutoff.

## Established operating-business results

Nine of the 11 companies have all 16 latest TTM features available. WSM has 15
available features and a resolved `not_meaningful` interest-coverage ratio because
the filing supports zero interest-bearing debt. COKE has 14 available features,
one structurally nonmeaningful capital-return result, and one unresolved interest
coverage ratio.

Amounts below are USD billions. These are observations, not a rank or investment
recommendation.

| Company | TTM end | Revenue growth | Operating margin | FCF | Interest coverage | Net debt | Pre-tax capital return |
|---|---|---:|---:|---:|---:|---:|---:|
| AMAT | 2026-07-26 | 7.8% | 29.6% | 5.62 | 33.00x | -0.49 | 40.2% |
| AMGN | 2026-06-30 | 9.1% | 30.0% | 10.18 | 4.28x | 43.31 | 20.7% |
| AMTM | 2026-07-03 | 11.4% | 4.2% | 0.47 | 1.98x | 3.37 | 7.3% |
| COKE | 2026-07-03 | 10.7% | 13.0% | 0.64 | unavailable | 2.34 | N/M |
| CW | 2026-06-30 | 10.5% | 18.8% | 0.63 | 16.20x | 0.48 | 20.8% |
| ESAB | 2026-07-03 | 9.7% | 12.1% | 0.20 | 3.54x | 2.18 | 9.5% |
| INTU | 2026-07-31 | 13.9% | 27.4% | 8.66 | 22.98x | 2.96 | 26.3% |
| MD | 2026-06-30 | 0.5% | 11.0% | 0.23 | 6.31x | 0.30 | 18.0% |
| QCOM | 2026-06-28 | 1.9% | 23.2% | 10.42 | 14.81x | 10.74 | 27.3% |
| UTHR | 2026-06-30 | 2.5% | 44.4% | 1.09 | 116.82x | -1.80 | 27.5% |
| WSM | 2026-08-02 | 2.2% | 19.2% | 1.34 | N/M | -1.03 | 135.1% |

WSM's unusually high capital-return approximation is surfaced with the existing
warning to inspect cash subtraction, lease obligations, and negative working
capital before comparison. COKE's capital result is `not_meaningful` because the
invested-capital denominator is non-positive. Neither result is converted into a
favorable or unfavorable score.

## Filing reconciliations

Most values come directly from SEC Company Facts. A small number of issuer-specific
interim lines were reconciled against the filed statements and are accepted only
when the exact accession, date interval, and filing date exist in the saved payload:

- AMTM and ESAB: interim `Interest expense and other, net`.
- COKE: common-equivalent diluted shares, including the split-adjusted comparative
  period needed for TTM share growth.
- QCOM: interim capital expenditures; total debt prefers a reported combined tag
  when present and otherwise sums current and long-term debt from the same filing.
- UTHR and WSM: explicit zero interest-bearing debt at the current and comparable
  quarterly balance-sheet dates.

The supporting primary filings are the
[AMTM 2026 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/2011286/000162828026055727/amtm-20260703.htm),
[ESAB 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1877322/000187732226000056/esab-20260703.htm),
[COKE 2025 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/317540/000031754025000070/coke-20250627.htm),
[COKE 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/317540/000162828026053370/coke-20260703.htm),
[QCOM 2026 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/804328/000080432826000086/qcom-20260628.htm),
[UTHR 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1082554/000108255426000027/uthr-20260630.htm), and
[WSM 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/719955/000071995526000208/wsm-20260802.htm).

COKE's annual normalization uses gross interest expense, while the interim filing
reports a net interest line. The workflow leaves TTM coverage unavailable rather
than mixing those definitions. AMTM and ESAB disclose that their coverage inputs
use a combined interest-and-other line.

## Reproduce the run

```bash
poetry run stocks-infer import-sec-development \
  --universe company_universe/growth-value-company-universe.xlsx \
  --ticker-map data/raw/sec-pilot/company_tickers_exchange.json \
  --company-facts-dir data/raw/sec-pilot \
  --as-of 2026-09-20 --retrieved-on 2026-09-20 \
  --output data/normalized/sec-development-quarterly-ttm-2026-09-20.json

poetry run stocks-infer research \
  --input data/normalized/sec-development-quarterly-ttm-2026-09-20.json \
  --as-of 2026-09-20 --output-root . \
  --run-id sec-development-quarterly-ttm-2026-09-20
```

The next implementation step is dated market-data import. Narrative thesis work
can then use annual evidence and the TTM trend layer together without collapsing
them into one score.
