"""Registry for built-in and externally supplied screening algorithms."""

from __future__ import annotations

from collections.abc import Iterable

from stocks_infer.algorithms.base import ScreeningAlgorithm


class AlgorithmRegistry:
    def __init__(self) -> None:
        self._algorithms: dict[str, ScreeningAlgorithm] = {}

    def register(self, algorithm: ScreeningAlgorithm) -> None:
        if not isinstance(algorithm, ScreeningAlgorithm):
            raise TypeError("algorithm does not satisfy the ScreeningAlgorithm contract")
        if not algorithm.slug or not algorithm.version:
            raise ValueError("algorithm slug and version are required")
        if algorithm.slug in self._algorithms:
            raise ValueError(f"algorithm already registered: {algorithm.slug}")
        self._algorithms[algorithm.slug] = algorithm

    def get(self, slug: str) -> ScreeningAlgorithm:
        try:
            return self._algorithms[slug]
        except KeyError as error:
            available = ", ".join(self.names()) or "none"
            raise KeyError(f"unknown algorithm '{slug}'; available: {available}") from error

    def select(self, slugs: Iterable[str] | None = None) -> tuple[ScreeningAlgorithm, ...]:
        if slugs is None:
            return self.all()
        return tuple(self.get(slug) for slug in slugs)

    def all(self) -> tuple[ScreeningAlgorithm, ...]:
        return tuple(self._algorithms[key] for key in self.names())

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._algorithms))
