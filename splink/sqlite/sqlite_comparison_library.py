from ..comparison_level_library import (
    _mutable_params,
)

from ..comparison_library import (  # noqa: F401
    ExactMatchBase,
    DistanceFunctionAtThresholdsComparisonBase,
)
from .sqlite_base import (
    SqliteBase,
)
from .sqlite_comparison_level_library import (
    else_level,
    distance_function_level,
)

_mutable_params["dialect"] = "sqlite"


class SqliteComparison(SqliteBase):
    @property
    def _else_level(self):
        return else_level


class exact_match(SqliteComparison, ExactMatchBase):
    pass


class distance_function_at_thresholds(
    SqliteComparison, DistanceFunctionAtThresholdsComparisonBase
):
    @property
    def _distance_level(self):
        return distance_function_level
