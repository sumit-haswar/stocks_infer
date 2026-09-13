"""Execution and consensus ranking for one or more screening algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from stocks_infer.algorithms.base import ScreeningAlgorithm, competition_ranks
from stocks_infer.models import ScreeningContext, ScreeningRecord, StockScore


@dataclass(frozen=True, slots=True)
class ScreeningRun:
    algorithm_scores: tuple[StockScore, ...]
    consensus_scores: tuple[StockScore, ...]
    shortlist: tuple[StockScore, ...]


class ScreeningRunner:
    """Run independent algorithms and combine their comparable scores."""

    consensus_slug = "consensus"
    consensus_version = "1.0.0"

    def __init__(self, algorithms: Sequence[ScreeningAlgorithm]) -> None:
        if not algorithms:
            raise ValueError("at least one algorithm is required")
        self.algorithms = tuple(algorithms)

    def run(
        self,
        records: Sequence[ScreeningRecord],
        *,
        as_of_date: date,
        shortlist_size: int,
        minimum_algorithms: int | None = None,
        parameters: Mapping[str, Any] | None = None,
    ) -> ScreeningRun:
        if shortlist_size < 1:
            raise ValueError("shortlist_size must be at least 1")
        self._validate_records(records, as_of_date)

        minimum = minimum_algorithms or len(self.algorithms)
        if not 1 <= minimum <= len(self.algorithms):
            raise ValueError("minimum_algorithms must be between 1 and algorithm count")

        context = ScreeningContext(
            as_of_date=as_of_date,
            records=tuple(records),
            parameters=parameters or {},
        )
        algorithm_scores = tuple(
            score
            for algorithm in self.algorithms
            for score in algorithm.run(context)
        )
        consensus = self._build_consensus(records, algorithm_scores, minimum)
        shortlist = tuple(score for score in consensus if score.eligible)[:shortlist_size]
        return ScreeningRun(
            algorithm_scores=algorithm_scores,
            consensus_scores=consensus,
            shortlist=shortlist,
        )

    def _build_consensus(
        self,
        records: Sequence[ScreeningRecord],
        algorithm_scores: Sequence[StockScore],
        minimum_algorithms: int,
    ) -> tuple[StockScore, ...]:
        scores_by_security: dict[str, list[StockScore]] = {
            record.security_id: [] for record in records
        }
        for score in algorithm_scores:
            scores_by_security[score.security_id].append(score)

        candidates: dict[str, tuple[ScreeningRecord, float, list[StockScore]]] = {}
        ineligible: list[StockScore] = []
        record_by_id = {record.security_id: record for record in records}

        for security_id, component_scores in scores_by_security.items():
            record = record_by_id[security_id]
            usable = [
                score
                for score in component_scores
                if score.eligible and score.score is not None
            ]
            if len(usable) < minimum_algorithms:
                warnings = [
                    f"Only {len(usable)} of {minimum_algorithms} required algorithms produced a score"
                ]
                warnings.extend(
                    f"{score.algorithm_slug}: {warning}"
                    for score in component_scores
                    if not score.eligible
                    for warning in score.warnings
                )
                ineligible.append(
                    StockScore(
                        algorithm_slug=self.consensus_slug,
                        algorithm_version=self.consensus_version,
                        security_id=record.security_id,
                        ticker=record.ticker,
                        eligible=False,
                        score=None,
                        rank=None,
                        warnings=tuple(warnings),
                    )
                )
                continue

            consensus_score = sum(score.score for score in usable) / len(usable)
            candidates[security_id] = (record, consensus_score, usable)

        ranks = competition_ranks(
            {security_id: values[1] for security_id, values in candidates.items()},
            higher_is_better=True,
        )
        results: list[StockScore] = []
        for security_id, (record, consensus_score, usable) in candidates.items():
            results.append(
                StockScore(
                    algorithm_slug=self.consensus_slug,
                    algorithm_version=self.consensus_version,
                    security_id=record.security_id,
                    ticker=record.ticker,
                    eligible=True,
                    score=round(consensus_score, 6),
                    rank=ranks[security_id],
                    reasons=tuple(
                        f"{score.algorithm_slug}: {score.score:.2f}"
                        for score in sorted(usable, key=lambda item: item.algorithm_slug)
                    ),
                    metrics_used={
                        "algorithm_count": float(len(usable)),
                        **{
                            f"score_{score.algorithm_slug}": score.score
                            for score in usable
                        },
                    },
                )
            )

        return tuple(
            sorted(results, key=lambda item: (item.rank or 0, item.ticker))
            + sorted(ineligible, key=lambda item: item.ticker)
        )

    def _validate_records(
        self, records: Sequence[ScreeningRecord], as_of_date: date
    ) -> None:
        seen: set[str] = set()
        for record in records:
            if record.security_id in seen:
                raise ValueError(f"duplicate security_id: {record.security_id}")
            if record.as_of_date != as_of_date:
                raise ValueError(f"as-of date mismatch for {record.ticker}")
            seen.add(record.security_id)
