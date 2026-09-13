# Stocks Infer Application Rework

**Discussion date:** September 12, 2026  
**Status:** Initial direction and architecture notes

## 1. Project Goal

Stocks Infer will be reworked into a dependable, explainable stock-screening application for publicly traded companies on NASDAQ and the NYSE.

The application is not intended to make an investment decision automatically. Its purpose is to reduce a large stock universe to a manageable list of promising companies. The final companies will be investigated and selected manually for potential long-term investment.

The target workflow is:

```text
NASDAQ/NYSE stock universe
        ↓
Fetch structured financial and market data
        ↓
Normalize the data into consistent financial metrics
        ↓
Run multiple pluggable screening algorithms
        ↓
Generate scores, ranks, explanations, and warnings
        ↓
Produce a shortlist for manual company analysis
```

The main investment focus is long-term growth at a reasonable valuation, with attention to business quality and financial strength.

## 2. Assessment of the Existing Repository

The existing project is an early proof of concept that:

1. Reads ticker symbols from lookup files or a hard-coded list.
2. Downloads Yahoo Finance summary and statistics web pages.
3. Parses financial values from HTML tables.
4. Stores selected values in PostgreSQL.
5. Runs a value-oriented ranking algorithm and exports a CSV file.

The original direction remains useful, but the implementation is no longer a reliable foundation because:

- It parses presentation-oriented Yahoo Finance HTML rather than consuming a structured data API.
- It depends on fixed HTML attributes such as `data-reactid`, which may change without notice.
- Required dependencies are not declared in `pyproject.toml`.
- Scraping failures are generally swallowed without useful diagnostics.
- The scraper processes only part of a hard-coded ticker list in its current form.
- Database queries do not reliably select the latest stored company snapshot.
- The database DDL contains stale or invalid index definitions.
- The ranking code contains an error that doubles the return-on-assets rank instead of combining it with the earnings-yield rank.
- The README and test coverage are minimal.

The application should therefore retain the product idea while replacing the current data collection, normalization, storage, and algorithm-running foundations.

## 3. Data Collection Direction

HTML scraping will be replaced with pluggable structured-data providers.

### 3.1 Provider responsibilities

The application should separate these responsibilities:

- **Universe provider:** supplies active NASDAQ and NYSE securities and their reference information.
- **Fundamentals provider:** supplies annual and quarterly financial statements or normalized financial facts.
- **Market-data provider:** supplies adjusted daily prices, volume, splits, and dividends.

Algorithms must not call providers directly. They should operate exclusively on normalized application data so that a provider can be replaced without rewriting the algorithms.

### 3.2 Candidate providers

The preferred authoritative source for reported financial statements is the SEC EDGAR API. It offers structured XBRL company facts, filing histories, and bulk downloads without requiring an API key. SEC data is authoritative and auditable, but translating inconsistent XBRL concepts into canonical metrics requires careful normalization.

A commercial normalized-data provider can be supported as an alternative or complement. Candidate services discussed include:

- Massive for US ticker reference data, market data, financial statements, and normalized ratios.
- Alpaca for the active US equity universe and market-price data.
- Alpha Vantage for normalized financial statements and historical prices.

The intended provider strategy is:

- Implement a provider-neutral interface.
- Begin with one practical provider combination.
- Preserve source metadata for every collected value.
- Make provider selection configurable.
- Avoid coupling algorithms to provider-specific field names.

Real-time market data is not necessary for this application. Adjusted daily or end-of-day prices are sufficient for long-term fundamental screening.

## 4. Stock Universe

The universe builder should select active common stocks whose primary listing is on NASDAQ or the NYSE.

The following filters should be configurable:

```yaml
exchanges:
  - NASDAQ
  - NYSE
security_types:
  - common_stock
include_adrs: false
exclude_etfs: true
exclude_funds: true
exclude_preferred_shares: true
exclude_units: true
exclude_rights: true
exclude_warrants: true
minimum_market_cap: 300000000
minimum_average_daily_dollar_volume: 1000000
```

The exact default thresholds have not yet been finalized.

The application should retain stable identifiers such as SEC CIK and FIGI in addition to the ticker. Tickers can change, so exchange listings and ticker history should be modeled separately from the underlying company.

Some algorithms may require their own eligibility rules. Banks, insurance companies, utilities, REITs, and other specialized industries should not automatically be judged using formulas designed for ordinary industrial companies.

## 5. Canonical Financial Data

Provider responses should be translated into a canonical set of application metrics. Likely metrics include:

- Revenue, gross profit, operating income, EBIT, EBITDA, and net income
- Operating cash flow, capital expenditure, and free cash flow
- Cash, debt, assets, liabilities, and shareholders' equity
- Diluted shares and diluted EPS
- Adjusted closing price and trading volume
- Market capitalization and enterprise value
- Revenue, EPS, and free-cash-flow growth
- Gross, operating, and net margins
- Return on invested capital, return on equity, and return on assets
- P/E, price-to-sales, price-to-book, EV/EBIT, EV/EBITDA, and free-cash-flow yield
- Debt ratios, liquidity ratios, and interest coverage

Every stored or materialized value should carry enough metadata to identify:

- Source provider
- Source filing or accession identifier, when available
- Fiscal period and period end date
- Filing or publication date
- Date on which the information became available
- Currency and unit
- Whether the metric was reported directly or calculated
- Data-quality warnings

The information availability date is particularly important. It prevents future information from leaking into historical screens and makes later evaluation or backtesting credible.

## 6. Storage Decision

PostgreSQL is not required for the initial workflow. Persistent storage is useful, but a persistent database server would currently introduce more operational overhead than value.

The initial implementation should use:

- Compressed JSON for optional raw provider-response caching.
- Parquet for normalized datasets and algorithm results.
- DuckDB for local analytical queries over Parquet files.
- CSV as a human-readable shortlist export, not as the primary data store.

A possible layout is:

```text
data/
  raw/
    2026-09-12/
      AAPL.json.gz
      MSFT.json.gz
  normalized/
    2026-09-12/
      <dataset-sha256>/
        screening_records.parquet

runs/
  2026-09-12/
    manifest.json
    all_scores.parquet
    shortlist.csv
```

Raw responses are useful for replaying normalization without repeatedly calling the provider. Whether they may be retained must also comply with the selected provider's licensing terms.

### 6.1 What each run should preserve

Each screening run should record:

- Run identifier and timestamp
- Effective data date
- SHA-256 fingerprint and path of the exact normalized input dataset
- Data-provider name and relevant dataset version
- Definition of the stock universe
- Complete list of included and excluded securities
- Algorithm names and versions
- Algorithm parameters
- Missing-data and exclusion counts
- Score, rank, reasons, and warnings for every evaluated security
- The final shortlist

Results for all evaluated stocks should be retained, not only the shortlisted companies. This makes it possible to understand why a company entered or left the shortlist and whether the cause was a price change, a new filing, a data correction, a universe change, or an algorithm change.

### 6.2 When PostgreSQL would become appropriate

PostgreSQL can be introduced later if the application gains:

- A web dashboard or external API
- Multiple users
- Concurrent collection and screening jobs
- Scheduled background workers
- Manual research notes and workflow states
- Larger or more frequently updated datasets
- A need for transactional updates shared by several processes

## 7. Pluggable Screening Algorithms

Screening algorithms should consume a complete normalized dataset and produce structured, explainable results. They must not fetch external data or depend on a particular persistence implementation.

A conceptual interface is:

```python
class ScreeningAlgorithm(Protocol):
    slug: str
    version: str

    def required_metrics(self) -> set[str]:
        ...

    def run(self, context: ScreeningContext) -> list[StockScore]:
        ...
```

The algorithm operates on the complete universe rather than one security at a time because many strategies depend on percentiles, ranks, sector comparisons, or cross-sectional normalization.

A result should be similarly explicit:

```python
@dataclass(frozen=True)
class StockScore:
    security_id: str
    ticker: str
    eligible: bool
    score: float | None
    rank: int | None
    reasons: list[str]
    warnings: list[str]
    metrics_used: dict[str, float]
```

Algorithms can initially be registered through an internal registry. If separately distributed plugins are needed later, the same interface can be exposed through Python package entry points such as `stocks_infer.algorithms`.

Algorithms must be versioned. Changing a formula, missing-value policy, weighting, universe rule, or threshold should create a distinguishable algorithm version so that old results remain reproducible.

## 8. Initial Algorithm Candidates

The first useful set should represent meaningfully different investment perspectives rather than small variations of the same formula.

### 8.1 Magic Formula

Rank companies using earnings yield and return on invested capital. The revised implementation should use carefully defined values such as EBIT/enterprise value and ROIC rather than the current approximation of EBITDA/enterprise value and return on assets.

### 8.2 Piotroski F-Score

Use the nine accounting signals covering profitability, leverage, liquidity, funding, and operating efficiency. This can serve as a financial-strength overlay for value candidates.

### 8.3 Quality and value composite

Combine metrics such as:

- Free-cash-flow yield
- ROIC
- Gross and operating margins
- Earnings and cash-flow stability
- Balance-sheet strength
- Conservative valuation multiples

### 8.4 Growth at a reasonable price

Combine metrics such as:

- Three- and five-year revenue growth
- Three- and five-year EPS or free-cash-flow growth
- Margin stability or expansion
- Cash conversion
- Return on incremental invested capital
- Valuation relative to growth and quality

Each algorithm should report why a stock passed, failed, or could not be evaluated. Missing data should never silently become a favorable score.

## 9. Combining Algorithm Results

The application should expose each algorithm's independent result as well as an optional consensus view.

The combined report may contain:

- Score and rank from each algorithm
- Number of algorithms that selected the company
- Consensus percentile or score
- Positive reasons
- Negative reasons and warnings
- Missing metrics
- Changes from the previous run

The consensus calculation should avoid double-counting highly correlated algorithms. A company selected by several genuinely different methods carries more information than one selected by several minor variations of the same value formula.

## 10. Collection and Screening Cadence

The proposed schedule is:

- Refresh the NASDAQ/NYSE universe monthly.
- Refresh prices weekly or monthly.
- Check for new fundamentals monthly and fetch only companies with new filings when possible.
- Run all screening algorithms monthly.
- Perform a deeper review around quarterly reporting periods.

A yearly run would miss important developments. Daily fundamental screening would usually add little value for a long-term strategy, although daily prices could be collected later if valuation monitoring requires them.

## 11. Proposed Implementation Sequence

The existing code can remain available as a reference while the new application foundation is built under a conventional `src/stocks_infer/` package.

The proposed sequence is:

1. Establish the package structure, configuration, logging, and tests.
2. Define canonical models and provider interfaces.
3. Implement the NASDAQ/NYSE universe collector.
4. Implement one fundamentals provider and one daily market-data provider.
5. Add raw response caching and normalized Parquet snapshots.
6. Add DuckDB queries for producing an algorithm-ready screening dataset.
7. Define the algorithm interface and plugin registry.
8. Implement Magic Formula and Piotroski F-Score as the first plugins.
9. Save complete scored results, run manifests, and CSV shortlists.
10. Compare successive runs and add manual review support.
11. Add a dashboard or PostgreSQL only when the workflow demonstrates a need for them.

## 12. Guiding Principles

The reworked application should follow these principles:

- **Structured sources over HTML scraping**
- **Provider independence**
- **Canonical and well-defined financial metrics**
- **Point-in-time correctness**
- **Reproducible and versioned runs**
- **Explainable algorithm results**
- **Explicit missing-data and eligibility policies**
- **Simple local operation before service infrastructure**
- **Human judgment as the final investment decision**

The immediate objective is not to build a trading system. It is to build a reliable research funnel that repeatedly narrows a broad US equity universe into a defensible list of long-term growth-and-value candidates.
