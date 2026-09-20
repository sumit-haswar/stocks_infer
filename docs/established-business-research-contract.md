# Established Business Research Contract

Framework: `established-operating/0.1.0`  
Features: `annual-features/0.1.0`  
Valuation: `fcff/0.1.0`

This is the first recorded-data implementation milestone of the
[research workflow plan](research-workflow-implementation-plan.md). It provides
a runnable research loop, not a completed or empirically validated investment
screen. All bundled examples are synthetic.

## Scope and routing

Start with manually classified operating companies. Classification includes a
date and written reason. At least three positive annual operating-income
observations among the latest five periods allow the established-business
framework. One recent loss does not automatically remove a company.

Banks, insurers, REITs, pre-revenue companies, other business types, and companies
marked cyclical are routed to framework review. Insufficient profitable history
also routes to review rather than a rejection. Raw features remain available,
but quality/growth/resilience assessments and DCF are withheld for these cases.
This simple routing rule is a provisional implementation choice, not a validated
definition of business maturity.

Classification is a dated snapshot in each input bundle. Correcting it requires
a new input/run. Full classification-history selection is not yet implemented;
replay the original bundle for the original classification.

## Input and evidence contract

The JSON bundle has `schema_version: 1` and arrays of `companies`, `sources`,
`facts`, `prices`, `theses`, and `scenarios`. See
[`research_watchlist.json`](../tests/fixtures/research_watchlist.json) for a complete
editable example; its generator documents the ten scenarios.

- Every fact has a stable fact ID, security ID, canonical metric, value, unit,
  period, availability date, source document, and source concept.
- Monetary facts are absolute currency units, not millions. Share counts are
  absolute shares. Currency conversion must occur before import.
- Capital expenditure and interest expense are positive outflow/expense amounts.
  Negative input amounts are rejected rather than silently sign-flipped.
- Financial sources preserve publication/retrieval dates and optional accessions.
- Non-finite values, unknown metrics, inconsistent units, duplicate IDs, and
  invalid references are rejected.
- Source publication cannot follow fact availability. Retrieval can happen later
  than the evaluation date: fetching an old filing today does not make it new
  information.
- The cutoff is end-of-day on `--as-of`, not an intraday trading simulation.
- Later revisions remain in the snapshot but cannot affect an earlier cutoff.
  For each metric/interval the latest available revision is used. Different
  values or intervals with the same latest availability date are marked invalid
  until reconciled. Equal duplicates choose a stable fact ID.
- Annual flow intervals must agree with the revenue interval. Comparative annual
  dates must be 330–400 days apart. Quarter and YTD facts can be preserved but
  never substituted for annual facts. Quarterly/TTM derivation is pending.
- Valuation prices must be unadjusted and supplied with shares on a consistent
  split basis, plus separate observation dates. The program rejects a declared
  adjusted-price series but cannot independently verify the supplied share basis.

Target six annual observations when possible: five display periods plus opening
balances. Available shorter histories are shown, never filled with zeros.
Annual data older than 550 days, prices older than seven days, or share counts
older than 180 days trigger explicit evidence warnings. These thresholds are
versioned operational defaults, not measures of investment merit.

## Features and formulas

The feature layer preserves actual input fact IDs, period, value, unit, status,
and the formula or explanation for unavailability. Annual features include:

| Feature | Definition / policy |
|---|---|
| Operating margin | Operating income / positive revenue |
| Cash conversion | Operating cash flow / positive net income |
| Free cash flow | Operating cash flow minus capex; equity cash-flow proxy, not FCFF |
| Revenue growth | Current / comparable prior annual revenue minus one |
| Share growth | Current / prior diluted weighted-average shares minus one |
| Interest coverage | Operating income / positive interest expense |
| Net debt | Debt minus cash |
| Pre-tax return on capital | Operating income / average opening and closing (debt + equity − cash) |

The capital-return approximation is explicitly **pre-tax**, not after-tax ROIC
or a claim to an exact Magic Formula definition. Both capital observations must
be positive; negative capital becomes `not_meaningful`, not a low score.
Zero-interest companies also have a nonmeaningful interest-coverage ratio, not
a zero or infinite coverage score. Share-count changes require split, acquisition,
and compensation context; the software does not assert they all represent dilution.

Feature states are `available`, `missing`, `invalid`, and `not_meaningful`.
There is no substitution, favorable imputation, or redistribution of weights.

## Independent assessments

No overall numerical score or rank is produced. The following provisional
checks organize investigation and must not be mistaken for empirical cutoffs:

| Dimension | Supportive observations |
|---|---|
| Quality | Positive operating margin, cash conversion ≥ 0.8x, pre-tax capital return ≥ 10% |
| Growth | Positive annual revenue growth and share growth ≤ 2% |
| Resilience | Positive operating cash flow and interest coverage ≥ 3x |

All observed checks supportive gives `supportive`. Supportive observations with
missing checks gives `incomplete`, never an upgraded score. Mixed favorable and
unfavorable observations gives `mixed`; all observed checks unfavorable gives
`concerns`; none available gives `insufficient_evidence`. Routing can override
these to `not_assessed` for an unsuitable framework. Missing-feature details are
always preserved separately in the evidence assessment.

Negative free cash flow adds a research question about maintenance versus
expansion investment and funding. It does not automatically lower quality or
remove the business. Negative equity adds an accounting-context question.
Interest coverage below 1x is a high-priority observation, even when quality
looks supportive. No distress probability is inferred.

Evidence coverage is a mechanical description of annual data, freshness, and
feature availability; it is not a numerical confidence probability. Quarterly
trends, debt maturities, competitive durability, and peer comparisons remain
manual research requirements.

## Narrative and valuation

Theses have dated versions, business economics, an opportunity, a research
decision, and the next review date. Claims require a source or an explicit
assumption label, counterargument, monitored metric, expected outcome, review
date, and invalidation condition. Claim sources cannot postdate the thesis.
Two thesis versions on the same date are rejected as ambiguous in this
date-resolution implementation.

Only the most recent thesis available by the cutoff is selected. Scenarios must
reference that exact thesis version and existing claim IDs. A new thesis does
not inherit old scenario assumptions silently. Missing scenarios are reported.

The researcher supplies five annual growth/margin assumptions, tax rate,
sales-to-capital ratio, discount rate, terminal growth, and terminal ROIC:

1. Revenue grows by the supplied annual rate.
2. NOPAT is operating income less tax on positive operating income. No automatic
   tax benefit is assumed for operating losses.
3. Incremental reinvestment is positive revenue change / sales-to-capital.
   Shrinking revenue does not automatically release cash.
4. FCFF is NOPAT minus incremental reinvestment, discounted for five years.
5. Terminal FCFF is terminal NOPAT × (1 − terminal growth / terminal ROIC).
6. Terminal value is terminal FCFF / (discount rate − terminal growth).
7. Equity value is enterprise value minus net debt. Value per share uses supplied
   current outstanding shares, with a zero floor on equity value per share.

Terminal growth must be nonnegative and below both discount rate and terminal
ROIC; terminal profitability must be positive. Sensitivity varies the discount
rate by ±1 percentage point where valid. Bear/base/bull labels are user-supplied
scenario names, not assigned probabilities or guaranteed ordered outcomes.

Limitations are shown on every scenario: future dilution is not modeled;
preferred stock, noncontrolling interests and other claims need bridge review;
maintenance investment is assumed covered by depreciation. Current share
count is distinct from annual diluted weighted-average shares. No automatic
maintenance-capex estimate or management forecast is invented.

## Research lists and review artifacts

- `framework_review`: other yardstick or classification/history review required.
- `evidence_needed`: incomplete annual features, stale market/fundamentals, or no
  usable base scenario.
- `investigate_weaknesses`: at least one mixed/concern assessment or negative FCF.
- `quality_at_potentially_attractive_price`: supportive quality and base-case
  value at least 15% above a sufficiently recent price, without interest
  coverage below 1x.
- `valuation_opportunity_needing_review`: the same scenario-relative valuation
  with mixed/incomplete quality evidence or interest coverage below 1x.
- `quality_price_watch`: supportive quality with less than 15% base-case upside
  and without interest coverage below 1x.
- `general_research`: fallback queue when none of the above applies.

Queues overlap. The 15% threshold is a transparent research-organizing heuristic,
not a validated margin of safety. CSV and report index order is ticker then
security ID; there is no implied ranking by investment merit.

Each run preserves normalized input JSON, all raw fact revisions in Parquet,
derived features in Parquet, full structured research JSON, a CSV comparison,
Markdown company reports, and a manifest with formula/framework/code fingerprints
and artifact hashes. Historical reports only display evidence available at the
cutoff; their replay input can retain future revisions. Existing run directories
are never overwritten. Replay requires the corresponding code/formula version
as well as saved inputs; the manifest fingerprints code but does not archive it.

`research-compare` verifies the saved artifacts and reports changes in financial
evidence, market data, thesis, valuations, research lists, and methodology.
It identifies changed categories; it does not claim causal attribution.

## Validation cases

| Synthetic example | Expected behavior |
|---|---|
| STEADY | Ordinary annual research and scenario comparison |
| EXPAND | Negative FCF stays visible alongside expansion questions |
| MISSING | Absent cash flow is unknown, not zero or favorable |
| BUYBACK | Negative equity makes capital-return interpretation unavailable |
| CYCLE | Route to a through-cycle framework |
| BANK | Route to a bank-specific framework |
| THIN | Insufficient history remains visible for research |
| STRESS | Interest-coverage warning remains prominent despite quality strength |
| DILUTE | Flag share-count changes for contextual review |
| RECOVER | One loss year does not erase the established profitable history |

Tests also cover later restatements, conflicting same-date facts, future
classification/thesis information, mismatched periods, quarter/annual mixing,
stale prices, incompatible price adjustments, evidence references, independent
valuation arithmetic, artifact integrity, and replay.

## Remaining work before the first release gate

1. SEC source ingestion, source-concept mappings, and reconciliation for an
   actual 10–15-company watchlist. Synthetic fixtures do not validate real XBRL.
2. Quarterly/YTD normalization and point-in-time TTM features, including fiscal
   calendars, amendments, and company-specific disclosures.
3. Sourced market CSV import and selection of an automated market-data adapter.
4. Actual research reviews to revise provisional thresholds and report design;
   peer-relative comparisons only after defining appropriate groups.
5. More complete valuation adjustments and narrative evidence where a business
   requires them. Add automated extraction only after manual workflow validation.

The next implementation priority is source normalization and real-company
reconciliation, not additional screening algorithms.
