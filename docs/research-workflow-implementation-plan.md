# Research Workflow: First Release Implementation Plan

Date: September 19, 2026

Implementation status: started. The first recorded-data milestone implements
annual historical facts, contextual assessments, manual thesis/scenario input,
reports, snapshots, and review comparisons. This does **not** satisfy the real
watchlist release gate yet. See
[the framework contract](established-business-research-contract.md) for the
implemented policies, validation cases, and remaining work.

## Objective

Build a complete research workflow for established, profitable operating
businesses. Start with a small watchlist and take it from historical data through
contextual assessment, a sourced investment thesis, valuation scenarios, and a
reviewable research report.

Build on the existing models, storage, registry, and CLI. The main additions are
historical data, contextual evaluation, and the research workflow.

## Product requirements

1. Use the appropriate yardstick for each business.
2. Include an algorithm only when it answers a useful research question.
3. Support overlapping research lists and separate assessment dimensions.
4. Do not automatically discard or underweight a company because one or two
   metrics look weak; distinguish context, severity, and missing evidence.
5. Connect narrative claims to financial evidence and valuation assumptions.

## First-release experience

The user supplies a watchlist and evaluation date. Each company receives:

- An explanation of the applicable evaluation framework.
- A historical financial profile with traceable calculations.
- Separate assessments of quality, growth, resilience, and valuation.
- Weaknesses, missing evidence, and questions requiring investigation.
- A thesis connecting business claims to measurable expectations.
- Bear, base, and bull valuation scenarios.
- Relevant research-list memberships and changes since the previous review.

The initial interface is a CLI with Markdown reports, CSV comparisons, and
editable structured research files. Existing fixture screening remains usable.

## 1. Research contract and example cases

Document the first framework and design its report before adding formulas.

- Define applicability for established operating businesses.
- Specify treatment of cyclicality, acquisitions, reinvestment, and unusual
  accounting.
- Define formulas, denominator policies, and minimum historical coverage.
- Separate missing, inapplicable, unfavorable, and unreliable evidence.
- Record manual classifications and adjustments with reasons.
- Select approximately 10–15 varied real companies for validation, plus
  synthetic edge cases: temporary negative free cash flow, declining margins,
  dilution, negative equity, and incomplete disclosures.

Acceptance: explain how every example is evaluated, which observations require
investigation, and which cases need another framework. Unsupported companies
remain visible with a routing explanation.

## 2. Historical data and provenance

Add models alongside existing snapshots:

| Model | Purpose |
|---|---|
| FinancialFact | Value, fiscal period, unit, source concept, filing, availability |
| MarketObservation | Dated price, share count, and adjustment metadata |
| SourceDocument | Filing/research source, publication and retrieval dates |
| FeatureValue | Derived metric, formula version, input references, warnings |
| FrameworkAssignment | Framework, reasons, and recorded manual override |

Target five annual periods and twelve quarters, retaining extra opening balances
needed by calculations. Shorter histories receive explicit coverage limitations.

Use SEC filings as the initial fundamentals source. SEC submissions and extracted
XBRL are available through JSON APIs:
[SEC developer resources](https://www.sec.gov/about/developer-resources).

Implement a sourced, dated market-data import contract first. Select an automated
price adapter after checking coverage and licensing. A CSV import can support
the workflow without requiring a paid subscription.

Rules:

- Preserve original and restated facts.
- Select only information available by the evaluation cutoff.
- Handle discrete-quarter versus year-to-date cash flows explicitly.
- Keep raw responses and normalized data.
- Distinguish valuation prices from adjusted return-series prices.

Acceptance: selected company statements reconcile to filings; later restatements
cannot silently alter earlier saved analyses.

## 3. Financial assessment framework

| Dimension | Initial evidence |
|---|---|
| Business quality | Capital returns, operating margins, cash conversion, consistency |
| Growth and reinvestment | Revenue/per-share growth, margin trajectory, investment requirements |
| Financial resilience | Cash, debt, interest coverage, cash generation, maturity information |
| Valuation | Earnings/cash-flow yields, relevant multiples, scenario value ranges |
| Evidence confidence | Coverage, freshness, reconciliation issues, unresolved adjustments |

Show levels, historical trends, and explanations. Use peer comparisons only
where groups are appropriate and sufficiently populated. Extend results beyond
`eligible: bool`: applicability, data sufficiency, observations, and risk severity
are separate concepts. Existing algorithms become supporting analyses when
applicable.

Acceptance: weak/missing metrics never silently eliminate a company or inflate
remaining scores. Serious funding concerns remain prominent despite strengths.

## 4. Narrative and evidence workflow

Store a versioned, initially file-editable thesis with:

- Business economics and proposed investment opportunity.
- Supporting claims and dated sources.
- Counterarguments and contradictory evidence.
- Expected milestones, review dates, and invalidation conditions.

Connect claims to observable measures. Expansion-spending claims should identify
expected capacity, revenue, margin, and cash-flow milestones.

Support manual research first. Later AI extraction produces cited drafts with
review status, not an authoritative narrative score.

Acceptance: material claims have evidence or are labeled assumptions; historical
reviews cannot use later documents or later-authored thesis versions.

## 5. Thesis-linked valuation scenarios

Implement a transparent valuation appropriate to the framework, with explicit
revenue growth, operating margins, taxes, reinvestment, discount rate, terminal
assumptions, net debt, and share count.

Produce bear/base/bull scenarios and sensitivity analysis. Link assumptions to
thesis claims. Expose unresolved assumptions instead of manufacturing precision.

Acceptance: independently checked calculations, correct enterprise-to-equity
conversion, explainable responses to assumption changes.

## 6. Research lists and review loop

| List | Purpose |
|---|---|
| Quality at a potentially attractive price | Prioritize deeper valuation research |
| Quality with demanding price expectations | Monitor price and business progress |
| Attractive candidate with unresolved concerns | Investigate specific weaknesses |
| Insufficient evidence | Identify missing research or data |

Lists can overlap. Sorting must be transparent; show all dimensions. Unavailable
assessments remain unranked and visible.

Save fingerprints, framework/formula versions, thesis version, scenario
assumptions, and reports. Compare reviews and distinguish new filings, prices,
assumptions, and methodology changes.

Acceptance: complete a review, record a decision and next review date, rerun
later, and understand what changed.

## Delivery order and release gate

Deliver six reviewable changes in the order above. Build an early end-to-end
example using recorded historical data during phases 2–3.

The first release is complete when:

- A real watchlist works through the entire workflow.
- Every displayed metric and material claim is traceable.
- Missing data and unsuitable formulas do not masquerade as poor performance.
- Saved inputs reproduce historical runs.
- Reports surface useful opportunities and unresolved concerns across examples.
- Existing fixture screening continues to work.

Financial normalization is the largest uncertainty and must be validated early
on contrasting businesses. Broader market screening, additional business
frameworks, automated narrative analysis, and return backtesting follow actual
use of this workflow. No performance advantage is assumed from adding formulas.
