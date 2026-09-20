# Hybrid Screening Algorithm Roadmap

This document refines the proposed hybrid approach for identifying long-term
value, growth, and growth-at-a-reasonable-price candidates from the NASDAQ and
NYSE stock universe.

## Important refinements

- Piotroski was specifically studied within high book-to-market value stocks,
  not as a universal quality score.
  [Piotroski paper](https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf)
- Mohanram is the complementary low book-to-market model, but much of its
  reported long-short performance came from identifying weak growth companies
  on the short side. We should be cautious about treating a high G-Score as a
  standalone buy signal.
  [Mohanram research](https://ideas.repec.org/a/spr/reaccs/v10y2005i2d10.1007_s11142-005-1526-4.html)
- Acquirer's Multiple substantially duplicates the valuation half of Magic
  Formula. Implementing both as independent votes would double-count EV/EBIT.
- QMJ includes profitability, growth, safety, and payout. It overlaps
  Piotroski, gross profitability, leverage, accruals, and dilution, so it should
  eventually be a composite framework rather than another equal vote.
  [AQR QMJ research](https://www.aqr.com/Insights/Research/Working-Paper/Quality-Minus-Junk)
- Altman and Ohlson are alternative distress models. Running both is useful
  diagnostically, but they should not count as two independent positive
  signals. Altman's original model was developed around manufacturing
  companies. [Altman paper](https://doi.org/10.1111/j.1540-6261.1968.tb00843.x),
  [Ohlson paper](https://www.jstor.org/stable/2490395)
- Beneish is a warning indicator, not a declaration of manipulation.
- Gross profitability is a useful independent quality measure and has research
  support as a complement to value.
  [Novy-Marx research](https://www.nber.org/papers/w15940)
- Momentum should use adjusted total-return history and remain a modest
  confirmation signal, not dominate a long-term fundamental screen.
  [Jegadeesh-Titman research](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)

## Recommended initial seven

The initial implementation should use this compact set:

| Role | Model |
|---|---|
| Value and efficiency | Magic Formula |
| Value-company quality | Piotroski F-Score |
| Growth-company quality | Mohanram G-Score |
| Broad profitability | Novy-Marx gross profitability |
| Earnings quality | Sloan accrual ratio |
| Distress protection | Altman Z-Score |
| Market confirmation | 12-1 momentum |

The following models can be added later:

- Beneish M-Score as a research warning
- QMJ as a more complete second-generation composite
- Ohlson as an alternative distress estimate
- Graham rules as a configurable conservative-value screen
- Acquirer's Multiple as an exposed metric within the value screen, rather than
  a separate vote

## Two screening lanes

Every company should not be forced through the same formula.

```text
Eligible NASDAQ/NYSE universe
             ↓
     Data-quality checks
             ↓
      ┌──────────────┴──────────────┐
      │                             │
Value-quality lane          Growth-quality lane
Magic Formula               Growth metrics
Piotroski                    Mohanram
Gross profitability         Gross profitability
Low accruals                Cash-flow quality
      │                             │
      └──────────────┬──────────────┘
                     ↓
          Distress and manipulation flags
                     ↓
             12-1 momentum context
                     ↓
         Value, growth, and GARP shortlists
```

This produces three useful views:

- Value shortlist
- Growth shortlist
- GARP shortlist: companies scoring well on both growth and valuation

A growth company should not automatically fail because it invests heavily in
R&D or issues shares strategically. Likewise, a distressed value company should
not rank highly merely because EV/EBIT is low.

## Algorithm result types

The plugin contract should evolve to distinguish:

- `RANKER`: produces a positive percentile score
- `FILTER`: determines eligibility
- `DIAGNOSTIC`: raises warnings
- `PENALTY`: reduces confidence without automatically excluding a company

For example:

| Algorithm | Type |
|---|---|
| Magic Formula | Ranker |
| Piotroski | Ranker |
| Mohanram | Ranker |
| Gross profitability | Ranker |
| Sloan accruals | Ranker or penalty |
| Altman | Filter or diagnostic |
| Beneish | Diagnostic |
| Momentum | Ranker or penalty |

This prevents a good Altman score from being treated as though it predicts
growth. It only says the company does not currently resemble the distress
profile captured by that model.

## Data-model implications

The current flat current/prior screening record is sufficient for the first two
algorithms but not the complete roadmap. The application will need:

- At least five annual financial periods
- At least twelve quarterly periods
- At least thirteen months of adjusted price history
- R&D, advertising, and capital expenditure
- Receivables and inventory
- Depreciation and SG&A
- Retained earnings
- Current and long-term assets and liabilities
- Share issuance and repurchases
- Industry classifications
- Point-in-time filing availability dates

The intended data flow is:

```text
Raw historical facts and price bars
              ↓
Point-in-time feature calculation
              ↓
Flat algorithm-ready ScreeningRecord
              ↓
Algorithms
```

`ScreeningRecord` can remain the algorithm input, but it should become a
materialized feature view generated from historical facts rather than the
primary historical representation.

## Next implementation slice

The provider-neutral screening foundation has been merged into `develop`. The
next implementation slice should:

1. Document the exact formula, required inputs, eligibility rules, and known
   limitations for each initial model.
2. Introduce historical financial-fact and adjusted-price-bar models.
3. Add a point-in-time feature calculation layer.
4. Extend the algorithm contract with ranker, filter, diagnostic, and penalty
   roles.
5. Implement additional models only after their inputs can be reproduced from
   the normalized historical data.
