# Twelve Data coverage trial

Trial date: 2026-09-27  
Price cutoff: 2026-09-26  
Requested history: 2007-01-01 through 2026-09-26  
Input: `data/normalized/sec-development-quarterly-ttm-2026-09-20.json`

## Result

Twelve Data returned daily, unadjusted price history for all 30 Development
companies. The final local report contains 126,098 observations, and every
series ends on the last trading day before the cutoff, 2026-09-25.

| Outcome | Companies | Meaning |
|---|---:|---|
| Passed automated checks | 22 | Exact ticker, USD currency, recent data, valid prices, and no material volume/flat-price anomaly |
| Review warning | 8 | Data was returned, but listing history, symbol resolution, or pre-listing records require an explicit boundary |
| API or coverage error | 0 | No company remained unavailable after symbol resolution |

The API key was sent only in the authorization header and does not appear in the
CSV or summary JSON. Detailed live output remains in the gitignored local file
`data/market/twelve-data-development-coverage-2026-09-26-final.csv`.

## Review warnings

| Ticker | Earliest row | Observations | Finding | Adapter rule |
|---|---|---:|---|---|
| AMTM | 2024-09-24 | 503 | Short history around the 2024 separation; regular-way trading began 2024-09-30 | Retain only dates supported by the security-history record |
| DUOL | 2021-07-28 | 1,297 | First row equals the IPO trading date | Accept from 2021-07-28 |
| ESAB | 2022-03-29 | 1,128 | Rows begin during the when-issued period; regular-way trading began 2022-04-05 | Mark when-issued rows or begin regular history on 2022-04-05 |
| NAVI | 2014-04-17 | 3,129 | Short history associated with its separation from SLM | Confirm the first regular-way trading date before historical evaluation |
| PECO | 2021-02-25 | 1,403 | 87 zero-volume rows and a 37-row flat price occur before the July 2021 Nasdaq IPO | Exclude all pre-IPO rows; reconcile the first accepted close independently |
| ROAD | 2018-05-04 | 2,110 | First row equals the IPO trading date | Accept from 2018-05-04 |
| SEI | 2017-05-12 | 2,356 | Short history associated with the original Solaris IPO | Confirm the listing boundary and retain the later ticker/name continuity |
| TPC | 2007-01-03 | 4,964 | Bare `TPC` is ambiguous across countries | Persist `TPC:NYSE` and require returned MIC `XNYS` |

The shorter histories are generally expected for later IPOs and spin-offs.
Company evidence confirms DUOL began trading on 2021-07-28, ROAD on 2018-05-04,
AMTM began regular-way trading on 2024-09-30, and ESAB on 2022-04-05. PECO is
the exception: its filing says its Nasdaq IPO closed on 2021-07-19, so the
provider's February-to-July records are not suitable public-market observations.

Sources:

- [Duolingo IPO announcement](https://investors.duolingo.com/news-releases/news-release-details/duolingo-announces-pricing-initial-public-offering)
- [Construction Partners IPO closing](https://ir.constructionpartners.net/news/press-releases/detail/45/construction-partners-inc-announces-closing-of-initial-public-offering)
- [Amentum separation completion](https://ir.amentum.com/news/news-details/2024/Amentum-Completes-Transformational-Combination-with-Jacobs-Critical-Mission-Solutions-and-Cyber-and-Intelligence-Units/default.aspx)
- [ESAB separation completion](https://investors.esabcorporation.com/news/news-details/2022/ESAB-Corporation-Completes-Separation-From-Enovis-and-Launches-as-an-Independent-Publicly-Traded-Company/default.aspx)
- [Phillips Edison 2023 Form 10-K](https://investors.phillipsedison.com/static-files/ec4ec2d2-1d0a-436b-b24d-c0e982163d8b)

## Corporate actions and identity

The `adjust=none` parameter behaved correctly across COKE's 10-for-1 split. The
2025-05-23 raw close was 1,143.55003, while the split-adjusted response was
114.355; both modes returned 112.93 after split-adjusted trading began on
2025-05-27. The company's announcement independently confirms that date and
ratio: [COKE split announcement](https://investor.cokeconsolidated.com/news-releases/news-release-details/coca-cola-consolidateds-10-1-stock-split-finalized-shares-trade).

COHR was checked for a ticker-history collision. Twelve Data's June-to-August
2022 values are consistent with II-VI, the continuing issuer in the bundle,
rather than the acquired legacy company that formerly used `COHR`. This agrees
with the issuer's announcement that II-VI changed its name and ticker from
`IIVI` to `COHR` on 2022-09-08:
[Coherent name and ticker change](https://www.coherent.com/news/press-releases/ii-vi-changes-name-to-coherent-and-launches-new-brand).

## Decision

Twelve Data is suitable as the provisional automated source for daily
unadjusted prices in this research workflow. It is not safe to import solely by
bare ticker or to assume every returned date is publicly traded history.
This is a technical coverage decision; plan terms and permitted local retention
must still be confirmed for the intended use before operational adoption.

The implemented adapter now:

1. Persist an exchange-qualified provider symbol and verify ticker, currency,
   exchange, and MIC on every response.
2. Join that symbol to the repository's stable CIK-based security ID.
3. Requests only a short current-snapshot window, so the historical IPO,
   spin-off, ticker-change, and when-issued boundaries remain controls for a
   future historical-return adapter rather than the current valuation snapshot.
4. Keeps the historical flat-price and zero-volume findings in this trial; the
   current snapshot requires a positive close and positive volume on the latest
   selected trading day inside its dated window.
5. Continue using dated SEC filings for outstanding shares.
6. Keep unadjusted valuation prices separate from any future adjusted
   total-return series.

The next execution step is to run the adapter, import its strict market CSV, and
reconcile one selected price, share count, and resulting market capitalization
for each of the 30 companies.
