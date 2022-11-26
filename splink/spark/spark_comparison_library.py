from ..comparison_level_library import (
    _mutable_params,
)


from ..comparison_library import (  # noqa: F401
    ExactMatchBase,
    DistanceFunctionAtThresholdsComparisonBase,
    LevenshteinAtThresholdsComparisonBase,
    JaroWinklerAtThresholdsComparisonBase,
    JaccardAtThresholdsComparisonBase,
    ArrayIntersectAtSizesComparisonBase,
)

from .spark_base import (
    SparkBase,
)
from .spark_comparison_level_library import (
    else_level,
    distance_function_level,
    levenshtein_level,
    jaro_winkler_level,
    jaccard_level,
    array_intersect_level,
)


_mutable_params["dialect"] = "spark"


class SparkComparison(SparkBase):
    @property
    def _else_level(self):
        return else_level


class exact_match(SparkComparison, ExactMatchBase):
    pass


class distance_function_at_thresholds(
    SparkComparison, DistanceFunctionAtThresholdsComparisonBase
):
    @property
    def _distance_level(self):
        return distance_function_level


class levenshtein_at_thresholds(SparkComparison, LevenshteinAtThresholdsComparisonBase):
    @property
    def _distance_level(self):
        return levenshtein_level


class jaro_winkler_at_thresholds(
    SparkComparison, JaroWinklerAtThresholdsComparisonBase
):
    @property
    def _distance_level(self):
        return jaro_winkler_level


class jaccard_at_thresholds(SparkComparison, JaccardAtThresholdsComparisonBase):
    @property
    def _distance_level(self):
        return jaccard_level


class array_intersect_at_sizes(SparkComparison, ArrayIntersectAtSizesComparisonBase):
    @property
    def _array_intersect_level(self):
        return array_intersect_level
