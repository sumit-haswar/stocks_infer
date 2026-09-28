# Development cohort: filing reconciliation and narrative pass

Date: September 22, 2026  
Evaluation cutoff retained: September 20, 2026

This pass preserves the original [30-company annual run](sec-development-run.md)
and creates a second replayable input and report after reconciling the balance
sheet debt definition for the 11 companies that reached the established
operating-business framework. The 60-company Evaluation set remains untouched.

- Normalized input: `data/normalized/sec-development-reconciled-2026-09-20.json`
- Reports: `research_runs/sec-development-reconciled-final-2026-09-20/`
- Run comparison: use `stocks-infer research-compare` against
  `research_runs/sec-development-2026-09-20/`

The new run contains 3,547 facts. The comparison identifies financial-evidence
changes for exactly the intended 11 companies. Six companies now have all 16
latest annual features needed by the current annual review: **AMAT, AMGN, CW,
INTU, MD, and UTHR**. This means their annual numerical evidence is complete
under the present contract; it does not mean their narrative, valuation, or
investment research is complete.

## Debt reconciliation

Canonical debt now means the filing-presented carrying amount of outstanding
interest-bearing borrowings, including current and noncurrent portions. The
bridge excludes operating-lease liabilities, undrawn credit capacity, letters
of credit, and marketable securities. A zero is imported only when the filing
explicitly supports zero outstanding borrowings. It is never inferred from an
absent XBRL tag.

| Ticker | Latest debt bridge (USD millions) | Net debt (cash) | Pre-tax capital return | Latest quality / growth / resilience |
|---|---:|---:|---:|---|
| AMAT | 6,555.0 | (686.0) | 44.8% | supportive / supportive / supportive |
| AMGN | 54,604.0 | 45,475.0 | 16.8% | supportive / supportive / supportive |
| AMTM | 3,943.0 | 3,506.0 | 5.7% | mixed / mixed / incomplete |
| COKE | 2,786.0 | 2,504.1 | not meaningful: negative equity | incomplete / incomplete / incomplete |
| CW | 957.9 | 586.5 | 20.3% | supportive / supportive / supportive |
| ESAB | 1,235.0 | 1,049.1 | 14.2% | supportive / supportive / incomplete |
| INTU | 7,669.0 | 2,964.0 | 26.3% | supportive / supportive / supportive |
| MD | 597.3 | 222.1 | 18.6% | supportive / concerns / supportive |
| QCOM | 14,811.0 | 9,291.0 | 38.9% | supportive / supportive / supportive |
| UTHR | 0.0 | (1,557.1) | 29.0% | supportive / supportive / supportive |
| WSM | 0.0 | (1,019.8) | 142.1% | supportive / supportive / incomplete |

Parentheses denote net cash. AMAT combines short-term debt with noncurrent
long-term debt. AMGN, AMTM, COKE, CW, INTU, and QCOM expose a usable total
carrying amount. ESAB and MD require current-plus-noncurrent bridges. UTHR's
[2025 10-K](https://www.sec.gov/Archives/edgar/data/1082554/000108255426000006/uthr-20251231.htm)
states that outstanding debt was zero; WSM's
[2025 10-K](https://www.sec.gov/Archives/edgar/data/719955/000071995526000059/wsm-20260201.htm)
reports no credit-facility borrowings and no debt on the balance sheet. The
other bridges reconcile to filing disclosures such as
[AMGN](https://www.sec.gov/Archives/edgar/data/318154/000031815426000010/amgn-20251231.htm),
[ESAB](https://www.sec.gov/Archives/edgar/data/1877322/000187732226000007/esab-20251231.htm),
[INTU](https://www.sec.gov/Archives/edgar/data/896878/000089687826000037/intu-20260731.htm),
and [QCOM](https://www.sec.gov/Archives/edgar/data/804328/000080432825000085/qcom-20250928.htm).

Debt reconciliation materially improved evidence coverage, but several ratios
still require judgment:

- WSM's 142.1% approximation subtracts cash while excluding about $1.46 billion
  of operating-lease liabilities. Treat it as an asset-light retail signal,
  not a directly comparable universal ROIC.
- UTHR held another $3.14 billion of current and noncurrent marketable
  investments beyond cash. The current `net_debt` feature deliberately does not
  add those securities. Its filing also describes borrowing and repaying a
  revolver during 2025, explaining why annual interest expense can coexist with
  zero year-end debt.
- INTU's $4.51 billion of restricted cash represents funds held for customers
  and is excluded from corporate cash. QCOM's $2.32 billion of restricted cash
  for its pending transaction is also excluded. Those are deliberate liquidity
  boundaries, not missing assets.
- COKE's capital-return approximation remains `not_meaningful` because book
  equity is negative. The other observed facts remain visible.
- ESAB, COKE, AMTM, and WSM still lack a comparable current interest-expense
  concept. Cash interest paid is not silently substituted for accrual interest
  expense.

## Narrative exceptions found in the filings

The numerical rules now add generic warnings for revenue or share-count changes
above 50%, net income materially above operating income, capital-return
approximations above 100%, and positive interest expense alongside zero
year-end debt. The filings explain why those warnings matter:

- **AMTM:** the 2024 Reverse Morris Trust transaction combined Amentum with the
  Jacobs Critical Mission Solutions business and issued roughly 142 million
  shares. Latest revenue growth of 71.6% and weighted-share growth of 168.1%
  are therefore transaction discontinuities, not clean organic growth or
  ordinary dilution. See the [Amentum 10-K](https://www.sec.gov/Archives/edgar/data/2011286/000162828025053993/amtm-20251003.htm).
- **DUOL:** 2025 net income of $414.1 million exceeds operating income of
  $135.6 million largely because the company released a valuation allowance and
  recorded a one-time $256.7 million income-tax benefit. The workflow keeps the
  company in maturity review rather than treating that net-income jump as
  recurring economics. See the [Duolingo 10-K](https://www.sec.gov/Archives/edgar/data/1562088/000162828026025737/duolingodecember312025an.htm).
- **MD:** the 4.9% revenue decline occurred after Pediatrix exited almost all
  office-based practices and its primary and urgent-care service line during
  2024. The growth concern is real at the consolidated level but needs a
  continuing-operations and portfolio-transition bridge. See the
  [Pediatrix 10-K](https://www.sec.gov/Archives/edgar/data/893949/000119312526058074/md-20251231.htm).
- **ANDE:** negative free cash flow of $56.1 million reflects $233.1 million of
  capital spending against $177.0 million of operating cash flow. Management
  attributes much of the increase to growth initiatives and says roughly half
  of planned 2026 capital spending is growth investment. That claim needs
  project-level return milestones; it does not erase weaker working-capital
  cash flow or earnings. See the [Andersons 10-K](https://www.sec.gov/Archives/edgar/data/821026/000082102626000010/ande-20251231.htm).
- **COHR:** negative free cash flow of about $1.02 billion combines $1.10
  billion of manufacturing-capacity additions with only $79.5 million of
  operating cash flow. The company describes capacity expansion for customer
  demand. Track utilization, working-capital normalization, and cash conversion
  rather than assigning an automatic failing score. See the
  [Coherent 10-K](https://www.sec.gov/Archives/edgar/data/820318/000082031826000020/iivi-20260630.htm).
- **SEI:** negative free cash flow of $437.7 million is primarily an expansion
  program: $646.8 million of 2025 capital expenditures, mostly for Power
  Solutions, financed partly with new debt. The narrative converts the alert
  into a milestone review of contracted capacity, deployment, utilization,
  operating cash generation, and leverage. See the
  [Solaris 10-K](https://www.sec.gov/Archives/edgar/data/1697500/000162828026012501/sei-20251231.htm).
- **NEO:** 10.1% revenue growth did not resolve the core concern. NeoGenomics
  reported a $115.9 million operating loss, only $5.2 million of operating cash
  flow, negative free cash flow, and operating income below interest expense.
  Its adjusted EBITDA becomes positive only after material add-backs. Keeping
  it in maturity/framework review is appropriate. See the
  [NeoGenomics 10-K](https://www.sec.gov/Archives/edgar/data/1077183/000107718326000010/neo-20251231.htm).

These findings demonstrate the intended hybrid workflow: the algorithm finds
the discontinuity or funding question, while the filing narrative determines
what the number means and which future evidence could confirm or contradict the
explanation. None of these notes supplies a valuation or an investment decision.

## Follow-up

The [annual normalization completion](sec-annual-normalization-completion.md)
resolves the filing-supported interest, share-count, and capex gaps, encodes
structurally nonmeaningful ratios explicitly, and freezes the lease and
cash-like-investment boundaries described above. Quarterly normalization,
market data, and sourced theses and scenarios remain before valuation work.

The held-out Evaluation set remains unopened.
