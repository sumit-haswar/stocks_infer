# Development cohort: annual normalization completion

Date: September 22, 2026  
Evaluation cutoff retained: September 20, 2026

This pass closes the latest-period annual normalization gaps for all 11
Development companies routed to the established operating-business framework.
It reruns the same 30 Development companies and does not inspect the 60-company
Evaluation set.

- Normalized input: `data/normalized/sec-development-annual-complete-2026-09-20.json`
- Reports: `research_runs/sec-development-annual-complete-2026-09-20/`
- Prior run: `research_runs/sec-development-reconciled-final-2026-09-20/`
- Facts: 3,561, an increase of 14 filing-reconciled observations
- Automated verification: 50 tests pass

## Filing-line reconciliations

SEC Company Facts exposes standardized taxonomy concepts but omits some
issuer-extension lines. The importer now carries a small reviewed filing-line table. 
A row is accepted only when its exact filing accession and annual interval also exist in the saved Company Facts payload.

| Company | Reconciled annual evidence | Latest result |
|---|---|---:|
| AMTM | Interest expense and other, net for 2023–2025 | $353.0m; 1.36x coverage |
| COKE | Gross interest expense for 2024–2025; common-equivalent diluted shares for 2023–2025 | $102.9m; 9.24x coverage; shares down 7.4% |
| ESAB | Interest expense and other, net for 2023–2025 | $83.9m; 4.91x coverage |
| QCOM | Capital expenditures for 2023–2025 | $1.192bn; $12.820bn free cash flow |

The evidence comes from the filed annual reports for
[Amentum](https://www.sec.gov/Archives/edgar/data/2011286/000162828025053993/amtm-20251003.htm),
[Coca-Cola Consolidated](https://www.sec.gov/Archives/edgar/data/317540/000162828026009057/coke-20251231.htm),
[ESAB](https://www.sec.gov/Archives/edgar/data/1877322/000187732226000007/esab-20251231.htm),
and [Qualcomm](https://www.sec.gov/Archives/edgar/data/804328/000080432825000085/qcom-20250928.htm).
The filing labels are retained in each fact's `source_concept` rather than
misrepresenting them as standardized US-GAAP tags.

## Resolved structural states

WSM has filing-supported zero debt and no reported interest expense. Its
interest coverage is now `not_meaningful` instead of `missing`, zero, or infinity.
COKE's pre-tax capital-return approximation remains `not_meaningful` because of
negative book equity. These states are resolved evidence: the workflow discloses
them and excludes them from the relevant assessment check. They do not receive
a favorable value and do not make the remaining observations incomplete.

After this change, every established-framework company has a resolved state for
all 16 latest annual features:

| Company | Quality | Growth | Resilience | Annual evidence |
|---|---|---|---|---|
| AMAT | supportive | supportive | supportive | available |
| AMGN | supportive | supportive | supportive | available |
| AMTM | mixed | mixed | mixed | incomplete: only four issuer periods |
| COKE | supportive | supportive | supportive | available; return on capital N/M |
| CW | supportive | supportive | supportive | available |
| ESAB | supportive | supportive | supportive | available |
| INTU | supportive | supportive | supportive | available |
| MD | supportive | concerns | supportive | available |
| QCOM | supportive | supportive | supportive | available |
| UTHR | supportive | supportive | supportive | available |
| WSM | supportive | supportive | supportive | available; coverage N/M |

`available` describes annual evidence coverage, not investment quality or a
completed research thesis. AMTM's current issuer history begins too recently to
meet the five-period evidence target even though its latest feature states are
resolved.

## Lease and cash boundaries

This release keeps operating leases outside debt and invested capital. A sound
lease-adjusted return would require adjusting both the liability and operating
income for rent; capitalizing only the liability would make comparisons less
consistent.

Net debt subtracts unrestricted corporate cash and cash equivalents. It does not
automatically count marketable investments as excess cash. Restricted cash and
customer funds remain excluded. Marketable securities can enter a later
valuation bridge only after a researcher reviews liquidity, operating needs,
taxes, and other claims. Every report with a computed net-debt feature states
this boundary explicitly.

## Reproduce and compare

```bash
poetry run stocks-infer import-sec-development \
  --universe company_universe/growth-value-company-universe.xlsx \
  --ticker-map data/raw/sec-pilot/company_tickers_exchange.json \
  --company-facts-dir data/raw/sec-pilot \
  --as-of 2026-09-20 --retrieved-on 2026-09-20 \
  --output data/normalized/sec-development-annual-complete-2026-09-20.json

poetry run stocks-infer research \
  --input data/normalized/sec-development-annual-complete-2026-09-20.json \
  --as-of 2026-09-20 --run-id sec-development-annual-complete-2026-09-20

poetry run stocks-infer research-compare \
  --before research_runs/sec-development-reconciled-final-2026-09-20 \
  --after research_runs/sec-development-annual-complete-2026-09-20
```

Quarterly/YTD and TTM normalization is now implemented in the
[quarterly and TTM pass](sec-quarterly-ttm-normalization.md). The remaining work
is dated market data and sourced thesis and scenario work. Specialized and
cyclical companies retain
their raw annual evidence but await their own yardsticks; their absent
operating-business features are not gaps to fill with inappropriate proxies.
