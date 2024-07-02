from ...comparison_level_library import (
    ArrayIntersectLevelBase,
    ColumnsReversedLevelBase,
    DamerauLevenshteinLevelBase,
    DatediffLevelBase,
    DistanceFunctionLevelBase,
    DistanceInKMLevelBase,
    ElseLevelBase,
    ExactMatchLevelBase,
    JaroLevelBase,
    JaroWinklerLevelBase,
    LevenshteinLevelBase,
    NullLevelBase,
    PercentageDifferenceLevelBase,
)
from ...comparison_library import (
    ArrayIntersectAtSizesBase,
    DamerauLevenshteinAtThresholdsBase,
    DatediffAtThresholdsBase,
    DistanceFunctionAtThresholdsBase,
    DistanceInKMAtThresholdsBase,
    ExactMatchBase,
    JaroAtThresholdsBase,
    JaroWinklerAtThresholdsBase,
    LevenshteinAtThresholdsBase,
)
from ...comparison_template_library import (
    DateComparisonBase,
    EmailComparisonBase,
    ForenameSurnameComparisonBase,
    NameComparisonBase,
    PostcodeComparisonBase,
)
from .postgres_base import (
    PostgresBase,
)


# Class used to feed our comparison_library classes
class PostgresComparisonProperties(PostgresBase):
    @property
    def _exact_match_level(self):
        return exact_match_level

    @property
    def _null_level(self):
        return null_level

    @property
    def _else_level(self):
        return else_level

    @property
    def _datediff_level(self):
        return datediff_level

    @property
    def _array_intersect_level(self):
        return array_intersect_level

    @property
    def _distance_in_km_level(self):
        return distance_in_km_level

    @property
    def _levenshtein_level(self):
        return levenshtein_level

    @property
    def _damerau_levenshtein_level(self):
        return damerau_levenshtein_level

    @property
    def _jaro_level(self):
        return jaro_level

    @property
    def _jaro_winkler_level(self):
        return jaro_winkler_level


#########################
### COMPARISON LEVELS ###
#########################
class null_level(PostgresBase, NullLevelBase):
    pass


class exact_match_level(PostgresBase, ExactMatchLevelBase):
    pass


class else_level(PostgresBase, ElseLevelBase):
    pass


class columns_reversed_level(PostgresBase, ColumnsReversedLevelBase):
    pass


class distance_function_level(PostgresBase, DistanceFunctionLevelBase):
    pass


class levenshtein_level(PostgresBase, LevenshteinLevelBase):
    pass


class damerau_levenshtein_level(PostgresBase, DamerauLevenshteinLevelBase):
    pass


class jaro_level(PostgresBase, JaroLevelBase):
    pass


class jaro_winkler_level(PostgresBase, JaroWinklerLevelBase):
    pass


class array_intersect_level(PostgresBase, ArrayIntersectLevelBase):
    pass


class percentage_difference_level(PostgresBase, PercentageDifferenceLevelBase):
    pass


class distance_in_km_level(PostgresBase, DistanceInKMLevelBase):
    pass


class datediff_level(PostgresBase, DatediffLevelBase):
    pass


##########################
### COMPARISON LIBRARY ###
##########################
class exact_match(PostgresComparisonProperties, ExactMatchBase):
    pass


class damerau_levenshtein_at_thresholds(
    PostgresComparisonProperties, DamerauLevenshteinAtThresholdsBase
):
    @property
    def _distance_level(self):
        return damerau_levenshtein_level


class distance_function_at_thresholds(
    PostgresComparisonProperties, DistanceFunctionAtThresholdsBase
):
    @property
    def _distance_level(self):
        return distance_function_level


class levenshtein_at_thresholds(
    PostgresComparisonProperties, LevenshteinAtThresholdsBase
):
    @property
    def _distance_level(self):
        return levenshtein_level


class jaro_at_thresholds(PostgresComparisonProperties, JaroAtThresholdsBase):
    @property
    def _distance_level(self):
        return self._jaro_level


class jaro_winkler_at_thresholds(
    PostgresComparisonProperties, JaroWinklerAtThresholdsBase
):
    @property
    def _distance_level(self):
        return self._jaro_winkler_level


class array_intersect_at_sizes(PostgresComparisonProperties, ArrayIntersectAtSizesBase):
    pass


class datediff_at_thresholds(PostgresComparisonProperties, DatediffAtThresholdsBase):
    pass


class distance_in_km_at_thresholds(
    PostgresComparisonProperties, DistanceInKMAtThresholdsBase
):
    pass


###################################
### COMPARISON TEMPLATE LIBRARY ###
###################################
# Not yet implemented
# Currently does not support the necessary comparison levels
# required for existing comparison templates
class date_comparison(PostgresComparisonProperties, DateComparisonBase):
    @property
    def _distance_level(self):
        return distance_function_level


class name_comparison(PostgresComparisonProperties, NameComparisonBase):
    @property
    def _distance_level(self):
        return distance_function_level


class forename_surname_comparison(
    PostgresComparisonProperties, ForenameSurnameComparisonBase
):
    @property
    def _distance_level(self):
        return distance_function_level


class postcode_comparison(PostgresComparisonProperties, PostcodeComparisonBase):
    pass


class email_comparison(PostgresComparisonProperties, EmailComparisonBase):
    @property
    def _distance_level(self):
        return distance_function_level
