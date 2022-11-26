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
from .duckb_base import (
    DuckDBBase,
)
from .duckdb_comparison_level_library import (
    else_level,
    distance_function_level,
    levenshtein_level,
    jaro_winkler_level,
    jaccard_level,
    array_intersect_level,
)

# _mutable_params["jaro_winkler"] = "jaro_winkler_similarity"
_mutable_params["dialect"] = "duckdb"


class DuckDBComparison(DuckDBBase):
    @property
    def _else_level(self):
        return else_level


class exact_match(DuckDBComparison, ExactMatchBase):
    pass


class distance_function_at_thresholds(
    DuckDBComparison, DistanceFunctionAtThresholdsComparisonBase
):
    @property
    def _distance_level(self):
        return distance_function_level


class levenshtein_at_thresholds(
    DuckDBComparison, LevenshteinAtThresholdsComparisonBase
):
    @property
    def _distance_level(self):
        return levenshtein_level


class jaro_winkler_at_thresholds(
    DuckDBComparison, JaroWinklerAtThresholdsComparisonBase
):
    @property
    def _distance_level(self):
        return jaro_winkler_level


class jaccard_at_thresholds(DuckDBComparison, JaccardAtThresholdsComparisonBase):
    @property
    def _distance_level(self):
        return jaccard_level


class array_intersect_at_sizes(DuckDBComparison, ArrayIntersectAtSizesComparisonBase):
    @property
    def _array_intersect_level(self):
        return array_intersect_level
