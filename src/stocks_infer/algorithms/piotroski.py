"""Piotroski F-Score implementation using current and prior normalized facts."""

from __future__ import annotations

from stocks_infer.algorithms.base import competition_ranks
from stocks_infer.models import ScreeningContext, ScreeningRecord, StockScore


class PiotroskiFScoreAlgorithm:
    slug = "piotroski_f_score"
    version = "1.0.0"
    description = "Scores nine profitability, leverage, liquidity, and efficiency signals."

    def required_metrics(self) -> frozenset[str]:
        return frozenset(
            {
                "net_income_ttm",
                "net_income_prior_ttm",
                "operating_cash_flow_ttm",
                "total_assets",
                "total_assets_prior",
                "current_assets",
                "current_assets_prior",
                "current_liabilities",
                "current_liabilities_prior",
                "long_term_debt",
                "long_term_debt_prior",
                "shares_outstanding",
                "shares_outstanding_prior",
                "gross_profit_ttm",
                "gross_profit_prior_ttm",
                "revenue_ttm",
                "revenue_prior_ttm",
            }
        )

    def run(self, context: ScreeningContext) -> tuple[StockScore, ...]:
        evaluated: dict[str, tuple[ScreeningRecord, tuple[tuple[str, bool], ...], dict[str, float]]] = {}
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

            invalid_denominators = self._invalid_denominators(record)
            if invalid_denominators:
                ineligible.append(
                    self._ineligible(
                        record,
                        f"Non-positive denominators: {', '.join(invalid_denominators)}",
                    )
                )
                continue

            metrics = self._derived_metrics(record)
            criteria = (
                ("Positive net income", record.net_income_ttm > 0),
                ("Positive operating cash flow", record.operating_cash_flow_ttm > 0),
                ("Return on assets improved", metrics["roa"] > metrics["roa_prior"]),
                ("Operating cash flow exceeds net income", record.operating_cash_flow_ttm > record.net_income_ttm),
                ("Long-term leverage declined", metrics["leverage"] < metrics["leverage_prior"]),
                ("Current ratio improved", metrics["current_ratio"] > metrics["current_ratio_prior"]),
                ("No share dilution", record.shares_outstanding <= record.shares_outstanding_prior),
                ("Gross margin improved", metrics["gross_margin"] > metrics["gross_margin_prior"]),
                ("Asset turnover improved", metrics["asset_turnover"] > metrics["asset_turnover_prior"]),
            )
            evaluated[record.security_id] = (record, criteria, metrics)

        raw_scores = {
            security_id: float(sum(passed for _, passed in values[1]))
            for security_id, values in evaluated.items()
        }
        ranks = competition_ranks(raw_scores, higher_is_better=True)

        results: list[StockScore] = []
        for security_id, (record, criteria, metrics) in evaluated.items():
            f_score = int(raw_scores[security_id])
            results.append(
                StockScore(
                    algorithm_slug=self.slug,
                    algorithm_version=self.version,
                    security_id=record.security_id,
                    ticker=record.ticker,
                    eligible=True,
                    score=round(100.0 * f_score / 9.0, 6),
                    rank=ranks[security_id],
                    reasons=tuple(
                        f"{'PASS' if passed else 'FAIL'}: {label}"
                        for label, passed in criteria
                    ),
                    metrics_used={"f_score": float(f_score), **metrics},
                )
            )

        return tuple(
            sorted(results, key=lambda item: (item.rank or 0, item.ticker))
            + sorted(ineligible, key=lambda item: item.ticker)
        )

    def _invalid_denominators(self, record: ScreeningRecord) -> tuple[str, ...]:
        names = (
            "total_assets",
            "total_assets_prior",
            "current_liabilities",
            "current_liabilities_prior",
            "revenue_ttm",
            "revenue_prior_ttm",
        )
        return tuple(name for name in names if getattr(record, name) <= 0)

    def _derived_metrics(self, record: ScreeningRecord) -> dict[str, float]:
        return {
            "roa": record.net_income_ttm / record.total_assets,
            "roa_prior": record.net_income_prior_ttm / record.total_assets_prior,
            "leverage": record.long_term_debt / record.total_assets,
            "leverage_prior": record.long_term_debt_prior / record.total_assets_prior,
            "current_ratio": record.current_assets / record.current_liabilities,
            "current_ratio_prior": record.current_assets_prior / record.current_liabilities_prior,
            "gross_margin": record.gross_profit_ttm / record.revenue_ttm,
            "gross_margin_prior": record.gross_profit_prior_ttm / record.revenue_prior_ttm,
            "asset_turnover": record.revenue_ttm / record.total_assets,
            "asset_turnover_prior": record.revenue_prior_ttm / record.total_assets_prior,
        }

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
