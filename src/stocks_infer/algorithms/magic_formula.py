"""Magic Formula-style ranking based on earnings yield and capital returns."""

from __future__ import annotations

from stocks_infer.algorithms.base import competition_ranks, percentile_score
from stocks_infer.models import ScreeningContext, ScreeningRecord, StockScore


class MagicFormulaAlgorithm:
    slug = "magic_formula"
    version = "1.0.0"
    description = "Ranks EBIT/enterprise value and EBIT/invested capital."

    def required_metrics(self) -> frozenset[str]:
        return frozenset({"ebit_ttm", "enterprise_value", "invested_capital"})

    def run(self, context: ScreeningContext) -> tuple[StockScore, ...]:
        eligible: dict[str, tuple[ScreeningRecord, float, float]] = {}
        ineligible: list[StockScore] = []

        for record in context.records:
            missing = sorted(
                metric
                for metric in self.required_metrics()
                if getattr(record, metric) is None
            )
            if missing:
                ineligible.append(
                    self._ineligible(record, f"Missing metrics: {', '.join(missing)}")
                )
                continue
            if record.enterprise_value <= 0:
                ineligible.append(
                    self._ineligible(record, "Enterprise value must be positive")
                )
                continue
            if record.invested_capital <= 0:
                ineligible.append(
                    self._ineligible(record, "Invested capital must be positive")
                )
                continue
            if record.ebit_ttm <= 0:
                ineligible.append(self._ineligible(record, "EBIT must be positive"))
                continue

            earnings_yield = record.ebit_ttm / record.enterprise_value
            return_on_capital = record.ebit_ttm / record.invested_capital
            eligible[record.security_id] = (
                record,
                earnings_yield,
                return_on_capital,
            )

        earnings_yields = {
            security_id: values[1] for security_id, values in eligible.items()
        }
        capital_returns = {
            security_id: values[2] for security_id, values in eligible.items()
        }
        earnings_ranks = competition_ranks(earnings_yields, higher_is_better=True)
        capital_ranks = competition_ranks(capital_returns, higher_is_better=True)
        combined_values = {
            security_id: float(earnings_ranks[security_id] + capital_ranks[security_id])
            for security_id in eligible
        }
        final_ranks = competition_ranks(combined_values, higher_is_better=False)

        count = len(eligible)
        results: list[StockScore] = []
        for security_id, (record, earnings_yield, return_on_capital) in eligible.items():
            rank = final_ranks[security_id]
            results.append(
                StockScore(
                    algorithm_slug=self.slug,
                    algorithm_version=self.version,
                    security_id=record.security_id,
                    ticker=record.ticker,
                    eligible=True,
                    score=percentile_score(rank, count),
                    rank=rank,
                    reasons=(
                        f"EBIT/enterprise value: {earnings_yield:.2%}",
                        f"EBIT/invested capital: {return_on_capital:.2%}",
                    ),
                    metrics_used={
                        "earnings_yield": earnings_yield,
                        "return_on_capital": return_on_capital,
                        "earnings_yield_rank": float(earnings_ranks[security_id]),
                        "return_on_capital_rank": float(capital_ranks[security_id]),
                        "combined_rank": combined_values[security_id],
                    },
                )
            )

        return tuple(
            sorted(results, key=lambda item: (item.rank or 0, item.ticker))
            + sorted(ineligible, key=lambda item: item.ticker)
        )

    def _ineligible(self, record: ScreeningRecord, warning: str) -> StockScore:
        return StockScore(
            algorithm_slug=self.slug,
            algorithm_version=self.version,
            security_id=record.security_id,
            ticker=record.ticker,
            eligible=False,
            score=None,
            rank=None,
            warnings=(warning,),
        )
