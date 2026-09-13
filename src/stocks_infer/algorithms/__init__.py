"""Built-in screening algorithms and their registry."""

from stocks_infer.algorithms.base import ScreeningAlgorithm
from stocks_infer.algorithms.magic_formula import MagicFormulaAlgorithm
from stocks_infer.algorithms.piotroski import PiotroskiFScoreAlgorithm
from stocks_infer.algorithms.registry import AlgorithmRegistry


registry = AlgorithmRegistry()
registry.register(MagicFormulaAlgorithm())
registry.register(PiotroskiFScoreAlgorithm())

__all__ = [
    "AlgorithmRegistry",
    "MagicFormulaAlgorithm",
    "PiotroskiFScoreAlgorithm",
    "ScreeningAlgorithm",
    "registry",
]
