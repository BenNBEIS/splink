# Script defining comparison templates that act as wrapper functions which produce
# comparisons based on the type of data in a column with default values to make
# it simpler to use splink out-of-the-box

from __future__ import annotations

import logging

from .comparison import Comparison  # change to self
from .comparison_level_composition import and_, or_
from .comparison_library_utils import (
    datediff_error_logger,
    distance_threshold_comparison_levels,
    distance_threshold_description,
)
from .input_column import InputColumn
from .misc import ensure_is_iterable

logger = logging.getLogger(__name__)


class DateComparisonBase(Comparison):
    def __init__(
        self,
        col_name,
        include_exact_match_level: bool = True,
        term_frequency_adjustments: bool = False,
        separate_1st_january: bool = False,
        levenshtein_thresholds: int | list = [1, 2],
        jaro_winkler_thresholds: float | list = [],
        datediff_thresholds: int | list = [1, 10],
        datediff_metrics: str | list = ["year", "year"],
        m_probability_exact_match: float = None,
        m_probability_1st_january: float = None,
        m_probability_or_probabilities_lev: float | list = None,
        m_probability_or_probabilities_jw: float | list = None,
        m_probability_or_probabilities_datediff: float | list = None,
        m_probability_else: float = None,
    ) -> Comparison:
        """A wrapper to generate a comparison for a date column the data in
        `col_name` with preselected defaults.

        The default arguments will give a comparison with comparison levels:\n
        - Exact match (1st of January only)\n
        - Exact match (all other dates)\n
        - Levenshtein distance <= 2\n
        - Date difference <= 1 year\n
        - Date difference <= 10 years \n
        - Anything else

        Args:
            col_name (str): The name of the column to compare
            include_exact_match_level (bool, optional): If True, include an exact match
                level. Defaults to True.
            term_frequency_adjustments (bool, optional): If True, apply term frequency
                adjustments to the exact match level. Defaults to False.
            separate_1st_january (bool, optional): If True, include a separate
                exact match comparison level when date is 1st January.
            levenshtein_thresholds (Union[int, list], optional): The thresholds to use
                for levenshtein similarity level(s).
                We recommend use of either levenshtein or jaro_winkler for fuzzy
                matching, but not both.
                Defaults to [2]
            jaro_winkler_thresholds (Union[int, list], optional): The thresholds to use
                for jaro_winkler similarity level(s).
                We recommend use of either levenshtein or jaro_winkler for fuzzy
                matching, but not both.
                Defaults to []
            datediff_thresholds (Union[int, list], optional): The thresholds to use
                for datediff similarity level(s).
                Defaults to [1, 1].
            datediff_metrics (Union[str, list], optional): The metrics to apply
                thresholds to for datediff similarity level(s).
                Defaults to ["month", "year"].
            m_probability_exact_match (_type_, optional): If provided, overrides the
                default m probability for the exact match level. Defaults to None.
            m_probability_or_probabilities_lev (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the levenshtein thresholds specified. Defaults to None.
            m_probability_or_probabilities_jw (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the jaro winkler thresholds specified. Defaults to None.
            m_probability_or_probabilities_datediff (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the datediff thresholds specified. Defaults to None.
            m_probability_else (_type_, optional): If provided, overrides the
                default m probability for the 'anything else' level. Defaults to None.


        Examples:
            >>> # DuckDB Basic Date Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.date_comparison("date_of_birth")

            >>> # DuckDB Bespoke Date Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.date_comparison(
            >>>                     "date_of_birth",
            >>>                     levenshtein_thresholds=[],
            >>>                     jaro_winkler_thresholds=[0.88],
            >>>                     datediff_thresholds=[1, 1],
            >>>                     datediff_metrics=["month", "year"])

            >>> # Spark Basic Date Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.date_comparison("date_of_birth")

            >>> # Spark Bespoke Date Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.date_comparison(
            >>>                     "date_of_birth",
            >>>                     levenshtein_thresholds=[],
            >>>                     jaro_winkler_thresholds=[0.88],
            >>>                     datediff_thresholds=[1, 1],
            >>>                     datediff_metrics=["month", "year"])

        Returns:
            Comparison: A comparison that can be inclued in the Splink settings
                dictionary.
        """
        # Construct Comparison
        comparison_levels = []
        comparison_levels.append(self._null_level(col_name))

        # Validate user inputs
        datediff_error_logger(thresholds=datediff_thresholds, metrics=datediff_metrics)

        if separate_1st_january:
            dob_first_jan = {
                "sql_condition": f"SUBSTR({col_name}_l, 6, 5) = '01-01'",
                "label_for_charts": "Date is 1st Jan",
            }
            comparison_level = {
                and_(
                    self._exact_match_level(col_name),
                    dob_first_jan,
                    label_for_charts="Exact match and 1st Jan",
                )
            }

            if m_probability_1st_january:
                comparison_level["m_probability"] = m_probability_1st_january
            if term_frequency_adjustments:
                comparison_level["tf_adjustment_column"] = col_name
            comparison_levels.append(comparison_level)

        if include_exact_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                term_frequency_adjustments=term_frequency_adjustments,
                m_probability=m_probability_exact_match,
            )
            comparison_levels.append(comparison_level)

        if len(levenshtein_thresholds) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                distance_function_name="levenshtein",
                distance_threshold_or_thresholds=levenshtein_thresholds,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_lev,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(jaro_winkler_thresholds) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                distance_function_name="jaro-winkler",
                distance_threshold_or_thresholds=jaro_winkler_thresholds,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_jw,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(levenshtein_thresholds) > 0 and len(jaro_winkler_thresholds) > 0:
            logger.warning(
                "You have included a comparison level for both Levenshtein and "
                "Jaro-Winkler similarity. We recommend choosing one or the other."
            )

        if len(datediff_thresholds) > 0:
            datediff_thresholds = ensure_is_iterable(datediff_thresholds)
            datediff_metrics = ensure_is_iterable(datediff_metrics)

            if m_probability_or_probabilities_datediff is None:
                m_probability_or_probabilities_datediff = [None] * len(
                    datediff_thresholds
                )
            m_probability_or_probabilities_datediff = ensure_is_iterable(
                m_probability_or_probabilities_datediff
            )

            for thres, metric, m_prob in zip(
                datediff_thresholds,
                datediff_metrics,
                m_probability_or_probabilities_datediff,
            ):
                comparison_level = self._datediff_level(
                    col_name,
                    date_threshold=thres,
                    date_metric=metric,
                    m_probability=m_prob,
                )
                comparison_levels.append(comparison_level)

        comparison_levels.append(
            self._else_level(m_probability=m_probability_else),
        )

        # Construct Description
        comparison_desc = ""
        if include_exact_match_level:
            comparison_desc += "Exact match vs. "

        if len(levenshtein_thresholds) > 0:
            comparison_desc += distance_threshold_description(
                col_name, "levenshtein", levenshtein_thresholds
            )

        if len(jaro_winkler_thresholds) > 0:
            comparison_desc += distance_threshold_description(
                col_name, "jaro-winkler", jaro_winkler_thresholds
            )

        if len(datediff_thresholds) > 0:
            datediff_desc = ", ".join(
                [
                    f"{m.title()}(s): {v}"
                    for v, m in zip(datediff_thresholds, datediff_metrics)
                ]
            )
            plural = "" if len(datediff_thresholds) == 1 else "s"
            comparison_desc += (
                f"Dates within the following threshold{plural} {datediff_desc} vs. "
            )

        comparison_desc += "anything else"

        comparison_dict = {
            "comparison_description": comparison_desc,
            "comparison_levels": comparison_levels,
        }
        super().__init__(comparison_dict)


class NameComparisonBase(Comparison):
    def __init__(
        self,
        col_name,
        include_exact_match_level: bool = True,
        phonetic_col_name: str = None,
        term_frequency_adjustments_name: str = False,
        term_frequency_adjustments_phonetic_name: str = False,
        levenshtein_thresholds: int | list = [],
        jaro_winkler_thresholds: float | list = [0.95, 0.88],
        jaccard_thresholds: float | list = [],
        m_probability_exact_match_name: float = None,
        m_probability_exact_match_phonetic_name: float = None,
        m_probability_or_probabilities_lev: float | list = None,
        m_probability_or_probabilities_jw: float | list = None,
        m_probability_or_probabilities_jac: float | list = None,
        m_probability_else: float = None,
    ) -> Comparison:
        """A wrapper to generate a comparison for a name column the data in
        `col_name` with preselected defaults.

        The default arguments will give a comparison with comparison levels:\n
        - Exact match \n
        - Jaro Winkler similarity >= 0.95\n
        - Jaro Winkler similarity >= 0.88\n
        - Anything else

        Args:
            col_name (str): The name of the column to compare
            include_exact_match_level (bool, optional): If True, include an exact match
                level for col_name. Defaults to True.
            phonetic_col_name (str): The name of the column with phonetic reduction
                (such as dmetaphone) of col_name. Including parameter will create
                an exact match level for  phonetic_col_name. The phonetic column must
                be present in the dataset to use this parameter.
                Defaults to None
            term_frequency_adjustments_name (bool, optional): If True, apply term
                frequency adjustments to the exact match level for "col_name".
                Defaults to False.
            term_frequency_adjustments_phonetic_name (bool, optional): If True, apply
                term frequency adjustments to the exact match level for
                "phonetic_col_name".
                Defaults to False.
            levenshtein_thresholds (Union[int, list], optional): The thresholds to use
                for levenshtein similarity level(s).
                Defaults to []
            jaro_winkler_thresholds (Union[int, list], optional): The thresholds to use
                for jaro_winkler similarity level(s).
                Defaults to [0.88]
            jaccard_thresholds (Union[int, list], optional): The thresholds to use
                for jaccard similarity level(s).
                Defaults to []
            m_probability_exact_match_name (_type_, optional): If provided, overrides
                the default m probability for the exact match level for col_name.
                Defaults to None.
            m_probability_exact_match_phonetic_name (_type_, optional): If provided,
                overrides the default m probability for the exact match level for
                phonetic_col_name. Defaults to None.
            m_probability_or_probabilities_lev (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_or_probabilities_datediff (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_else (_type_, optional): If provided, overrides the
                default m probability for the 'anything else' level. Defaults to None.

        Examples:
            >>> # DuckDB Basic Name Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.name_comparison("name")

            >>> # DuckDB Bespoke Name Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.name_comparison("name",
            >>>                     phonetic_col_name = "name_dm",
            >>>                     term_frequency_adjustments_name = True,
            >>>                     levenshtein_thresholds=[2],
            >>>                     jaro_winkler_thresholds=[],
            >>>                     jaccard_thresholds=[1]
            >>>                     )

            >>> # Spark Basic Name Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.name_comparison("name")

            >>> # Spark Bespoke Date Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.name_comparison("name",
            >>>                     phonetic_col_name = "name_dm",
            >>>                     term_frequency_adjustments_name = True,
            >>>                     levenshtein_thresholds=[2],
            >>>                     jaro_winkler_thresholds=[],
            >>>                     jaccard_thresholds=[1]
            >>>                     )

        Returns:
            Comparison: A comparison that can be included in the Splink settings
                dictionary.
        """
        # Construct Comparison
        comparison_levels = []
        comparison_levels.append(self._null_level(col_name))

        if include_exact_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                term_frequency_adjustments=term_frequency_adjustments_name,
                m_probability=m_probability_exact_match_name,
                include_colname_in_charts_label=True,
            )
            comparison_levels.append(comparison_level)

            if phonetic_col_name is not None:
                comparison_level = self._exact_match_level(
                    phonetic_col_name,
                    term_frequency_adjustments=term_frequency_adjustments_phonetic_name,
                    m_probability=m_probability_exact_match_phonetic_name,
                    include_colname_in_charts_label=True,
                )
                comparison_levels.append(comparison_level)

        if len(levenshtein_thresholds) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                distance_function_name="levenshtein",
                distance_threshold_or_thresholds=levenshtein_thresholds,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_lev,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(jaro_winkler_thresholds) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                distance_function_name="jaro-winkler",
                distance_threshold_or_thresholds=jaro_winkler_thresholds,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_jw,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(jaccard_thresholds) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                distance_function_name="jaccard",
                distance_threshold_or_thresholds=jaccard_thresholds,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_jac,
            )
            comparison_levels = comparison_levels + threshold_levels

        comparison_levels.append(
            self._else_level(m_probability=m_probability_else),
        )

        # Construct Description
        comparison_desc = ""
        if include_exact_match_level:
            comparison_desc += "Exact match vs. "

        if phonetic_col_name is not None:
            comparison_desc += "Names with phonetic exact match vs. "

        if len(levenshtein_thresholds) > 0:
            comparison_desc += distance_threshold_description(
                col_name, "levenshtein", levenshtein_thresholds
            )

        if len(jaro_winkler_thresholds) > 0:
            comparison_desc += distance_threshold_description(
                col_name, "jaro-winkler", jaro_winkler_thresholds
            )

        if len(jaccard_thresholds) > 0:
            comparison_desc += distance_threshold_description(
                col_name, "jaccard", jaccard_thresholds
            )

        comparison_desc += "anything else"

        comparison_dict = {
            "comparison_description": comparison_desc,
            "comparison_levels": comparison_levels,
        }
        super().__init__(comparison_dict)


class ForenameSurnameComparisonBase(Comparison):
    def __init__(
        self,
        forename_col_name,
        surname_col_name,
        include_exact_match_level: bool = True,
        include_columns_reversed: bool = True,
        term_frequency_adjustment_col_forename_and_surname: str = None,
        phonetic_forename_col_name: str = None,
        phonetic_surname_col_name: str = None,
        term_frequency_adjustments_col_phonetic_forename_and_surname: str = None,
        term_frequency_adjustments_forename: bool = True,
        term_frequency_adjustments_surname: bool = True,
        term_frequency_adjustments_phonetic_forename: bool = True,
        term_frequency_adjustments_phonetic_surname: bool = True,
        levenshtein_thresholds_surname: int | list = [],
        jaro_winkler_thresholds_surname: float | list = [0.88],
        jaccard_thresholds_surname: float | list = [],
        levenshtein_thresholds_forename: int | list = [],
        jaro_winkler_thresholds_forename: float | list = [0.88],
        jaccard_thresholds_forename: float | list = [],
        m_probability_exact_match_forename_surname: float = None,
        m_probability_exact_match_phonetic_forename_surname: float = None,
        m_probability_columns_reversed_forename_surname: float = None,
        m_probability_exact_match_surname: float = None,
        m_probability_exact_match_forename: float = None,
        m_probability_exact_match_phonetic_surname: float = None,
        m_probability_exact_match_phonetic_forename: float = None,
        m_probability_or_probabilities_surname_lev: float | list = None,
        m_probability_or_probabilities_surname_jw: float | list = None,
        m_probability_or_probabilities_surname_jac: float | list = None,
        m_probability_or_probabilities_forename_lev: float | list = None,
        m_probability_or_probabilities_forename_jw: float | list = None,
        m_probability_or_probabilities_forename_jac: float | list = None,
        m_probability_else: float = None,
    ) -> Comparison:
        """A wrapper to generate a comparison for a name column the data in
        `col_name` with preselected defaults.

        The default arguments will give a comparison with comparison levels:\n
        - Exact match forename and surname\n
        - Macth of forename and surname reversed\n
        - Exact match surname\n
        - Exact match forename\n
        - Fuzzy match surname (levensthtein <=2 or jaro-winkler >= 0.88)\n
        - Fuzzy match forename ((levensthtein <=2 or jaro-winkler>=  0.88)\n
        - Anything else

        Args:
            forename_col_name (str): The name of the forename column to compare
            surname_col_name (str): The name of the surname column to compare
            include_exact_match_level (bool, optional): If True, include an exact match
                level for col_name. Defaults to True.
            include_columns_reversed (bool, optional): If True, include a comparison
                level for forename and surname being swapped. Defaults to True
            term_frequency_adjustment_col_forename_and_surname (str, optional): The name
                of a combined forename surname column. This column is used to provides
                term frequency adjustments for forename surname exact match and columns
                reversed levels.
                Defaults to None
            phonetic_forename_col_name (str, optional): The name of the column with
                phonetic reduction (such as dmetaphone) of forename_col_name. Including
                parameter will create an exact match level for  phonetic_forename_col_name.
                The phonetic column must be present in the dataset to use this parameter.
                Defaults to None
            phonetic_surname_col_name (str, optional): The name of the column with phonetic
                reduction (such as dmetaphone) of surname_col_name. Including parameter
                will create an exact match level for  phonetic_surname_col_name. The
                phonetic column must be present in the dataset to use this parameter.
                Defaults to None
            term_frequency_adjustments_col_phonetic_forename_and_surname (str, optional):
                The name a combined forename surname column. This column is used to
                provides term frequency adjustments for forename surname phonetic match
                level.
                Defaults to None
            term_frequency_adjustments_forename (bool, optional): If True, apply term
                frequency adjustments to the exact match level for forename_col_name.
                Defaults to False.
            term_frequency_adjustments_surname (bool, optional): If True, apply term
                frequency adjustments to the exact match level for surname_col_name.
                Defaults to False.
            term_frequency_adjustments_forename (bool, optional): If True, apply term
                frequency adjustments to the exact match level for
                phonetic_forename_col_name.
                Defaults to False.
            term_frequency_adjustments_surname (bool, optional): If True, apply term
                frequency adjustments to the exact match level for
                phonetic_surname_col_name.
                Defaults to False.
            levenshtein_thresholds_surname (Union[int, list], optional): The thresholds
                to use for levenshtein similarity level(s) for surname_col_name.
                Defaults to []
            jaro_winkler_thresholds_surname (Union[int, list], optional): The thresholds
                to use for jaro_winkler similarity level(s) for surname_col_name.
                Defaults to [0.88]
            jaccard_thresholds_surname (Union[int, list], optional): The thresholds to
                use for jaccard similarity level(s) for surname_col_name.
                Defaults to []
            levenshtein_thresholds_forename (Union[int, list], optional): The thresholds
                to use for levenshtein similarity level(s) for forename_col_name.
                Defaults to []
            jaro_winkler_thresholds_forename (Union[int, list], optional): The thresholds
                to use for jaro_winkler similarity level(s) for forename_col_name.
                Defaults to [0.88]
            jaccard_thresholds_forename (Union[int, list], optional): The thresholds to
                use for jaccard similarity level(s) for forename_col_name.
                Defaults to []
            m_probability_exact_match_forename_surname (_type_, optional): If provided,
                overrides the default m probability for the exact match level for
                forename and surname.
                Defaults to None.
            m_probability_exact_match_phonetic_forename_surname (_type_, optional): If
                provided, overrides the default m probability for the phonetic match
                level for forename and surname.
                Defaults to None.
            m_probability_columns_reversed_forename_surname (_type_, optional): If
                provided, overrides the default m probability for the columns reversed
                level for forename and surname.
                Defaults to None.
            m_probability_columns_reversed_forename_surname (_type_, optional): If
                provided, overrides the default m probability for the columns reversed
                level for forename and surname.
                Defaults to None.
            m_probability_exact_match_surname (_type_, optional): If provided,
                overrides the default m probability for the surname exact match
                level for forename and surname.
                Defaults to None.
            m_probability_exact_match_forename (_type_, optional): If provided,
                overrides the default m probability for the forename exact match
                level for forename and forename.
                Defaults to None.
            m_probability_phonetic_match_surname (_type_, optional): If provided,
                overrides the default m probability for the surname phonetic match
                level for forename and surname.
                Defaults to None.
            m_probability_phonetic_match_forename (_type_, optional): If provided,
                overrides the default m probability for the forename phonetic match
                level for forename and forename.
                Defaults to None.
            m_probability_or_probabilities_surname_lev (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_or_probabilities_surname_jw (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_or_probabilities_surname_jac (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_or_probabilities_forename_lev (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_or_probabilities_forename_jw (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_or_probabilities_forename_jac (Union[float, list], optional):
                _description_. If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_else (_type_, optional): If provided, overrides the
                default m probability for the 'anything else' level. Defaults to None.

        Examples:
            >>> # DuckDB Basic Forename Surname Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> ctl.forename_surname_comparison("first_name", "surname)

            >>> # Spark Basic Forename Surname Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> ctl.forename_surname_comparison("first_name", "surname)


        Returns:
            Comparison: A comparison that can be included in the Splink settings
                dictionary.
        """
        # Create InputColumns for instances when not using cll functions

        forename_col = InputColumn(forename_col_name, sql_dialect=self._sql_dialect)
        forename_col_l, forename_col_r = forename_col.names_l_r()
        surname_col = InputColumn(surname_col_name, sql_dialect=self._sql_dialect)
        surname_col_l, surname_col_r = surname_col.names_l_r()
        # if term_frequency_adjustment_col_forename_and_surname:
        #    forename_surname_col = InputColumn(
        #               term_frequency_adjustment_col_forename_and_surname,
        #               sql_dialect=self._sql_dialect
        #               )
        #    forename_surname_col_l, ful_name_col_r = forename_surname_col.names_l_r()
        # else:
        #    forename_surname_col = None

        if phonetic_forename_col_name:
            phonetic_forename_col = InputColumn(
                phonetic_forename_col_name, sql_dialect=self._sql_dialect
            )
            (
                phonetic_forename_col_l,
                phonetic_forename_col_r,
            ) = phonetic_forename_col.names_l_r()
        if phonetic_surname_col_name:
            phonetic_surname_col = InputColumn(
                phonetic_surname_col_name, sql_dialect=self._sql_dialect
            )
            (
                phonetic_surname_col_l,
                phonetic_surname_col_r,
            ) = phonetic_surname_col.names_l_r()

        # Construct Comparison
        comparison_levels = []

        comparison_level = or_(
            self._null_level("forename"),
            self._null_level("surname"),
            label_for_charts="Null",
        )

        comparison_levels.append(comparison_level)

        ### Forename surname exact match

        if include_exact_match_level:
            comparison_level = {
                "sql_condition": f"{forename_col_l} = {forename_col_r} "
                f"AND {surname_col_l} = {surname_col_r}",
                "tf_adjustment_column": term_frequency_adjustment_col_forename_and_surname,
                "tf_adjustment_weight": 1.0,
                "m_probability": m_probability_exact_match_forename_surname,
                "label_for_charts": "Full name exact match",
            }

            comparison_levels.append(comparison_level)

        ### Phonetic forename surname match

        if phonetic_forename_col_name and phonetic_surname_col_name is not None:
            comparison_level = {
                "sql_condition": f"{phonetic_forename_col_l}={phonetic_forename_col_r}"
                f" AND {phonetic_surname_col_l} = {phonetic_surname_col_r}",
                "tf_adjustment_column": term_frequency_adjustments_col_phonetic_forename_and_surname,
                "tf_adjustment_weight": 1.0,
                "m_probability": m_probability_exact_match_phonetic_forename_surname,
                "label_for_charts": "Full name phonetic match",
            }
            comparison_levels.append(comparison_level)

        ### Columns reversed match

        if include_columns_reversed:
            comparison_level = self._columns_reversed_level(
                forename_col_name,
                surname_col_name,
                tf_adjustment_column=term_frequency_adjustment_col_forename_and_surname,
                m_probability=m_probability_columns_reversed_forename_surname,
            )
            comparison_levels.append(comparison_level)

        ### Surname Exact match

        comparison_level = self._exact_match_level(
            surname_col_name,
            term_frequency_adjustments=term_frequency_adjustments_surname,
            m_probability=m_probability_exact_match_forename,
            include_colname_in_charts_label=True,
        )
        comparison_levels.append(comparison_level)

        ### Forename Exact match

        comparison_level = self._exact_match_level(
            forename_col_name,
            term_frequency_adjustments=term_frequency_adjustments_forename,
            m_probability=m_probability_exact_match_forename,
            include_colname_in_charts_label=True,
        )
        comparison_levels.append(comparison_level)

        ### Surname Fuzzy match
        if len(levenshtein_thresholds_surname) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                surname_col_name,
                distance_function_name="levenshtein",
                distance_threshold_or_thresholds=levenshtein_thresholds_surname,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_surname_lev,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(jaro_winkler_thresholds_surname) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                surname_col_name,
                distance_function_name="jaro-winkler",
                distance_threshold_or_thresholds=jaro_winkler_thresholds_surname,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_surname_jw,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(jaccard_thresholds_surname) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                surname_col_name,
                distance_function_name="jaccard",
                distance_threshold_or_thresholds=jaccard_thresholds_surname,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_surname_jac,
            )
            comparison_levels = comparison_levels + threshold_levels

        ### Forename Fuzzy match

        if len(levenshtein_thresholds_forename) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                forename_col_name,
                distance_function_name="levenshtein",
                distance_threshold_or_thresholds=levenshtein_thresholds_forename,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_forename_lev,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(jaro_winkler_thresholds_forename) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                forename_col_name,
                distance_function_name="jaro-winkler",
                distance_threshold_or_thresholds=jaro_winkler_thresholds_forename,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_forename_jw,
            )
            comparison_levels = comparison_levels + threshold_levels

        if len(jaccard_thresholds_forename) > 0:
            threshold_levels = distance_threshold_comparison_levels(
                self,
                forename_col_name,
                distance_function_name="jaccard",
                distance_threshold_or_thresholds=jaccard_thresholds_forename,
                m_probability_or_probabilities_thres=m_probability_or_probabilities_forename_jac,
            )
            comparison_levels = comparison_levels + threshold_levels

        comparison_levels.append(
            self._else_level(m_probability=m_probability_else),
        )

        # Construct Description
        comparison_desc = ""
        if include_exact_match_level:
            comparison_desc += "Exact match vs. "

        if phonetic_forename_col_name and phonetic_surname_col_name is not None:
            comparison_desc += "Phonetic match forename and surname vs. "

        if include_columns_reversed:
            comparison_desc += "Forename and surname columns reversed vs. "

        comparison_desc += "Surname exact match vs. "

        comparison_desc += "Forename exact match vs. "

        if len(levenshtein_thresholds_surname) > 0:
            comparison_desc += distance_threshold_description(
                surname_col_name, "levenshtein", levenshtein_thresholds_surname
            )

        if len(jaro_winkler_thresholds_surname) > 0:
            comparison_desc += distance_threshold_description(
                surname_col_name, "jaro-winkler", jaro_winkler_thresholds_surname
            )

        if len(jaccard_thresholds_surname) > 0:
            comparison_desc += distance_threshold_description(
                surname_col_name, "jaccard", jaccard_thresholds_surname
            )

        if len(levenshtein_thresholds_forename) > 0:
            comparison_desc += distance_threshold_description(
                forename_col_name, "levenshtein", levenshtein_thresholds_forename
            )

        if len(jaro_winkler_thresholds_forename) > 0:
            comparison_desc += distance_threshold_description(
                forename_col_name, "jaro-winkler", jaro_winkler_thresholds_forename
            )

        if len(jaccard_thresholds_forename) > 0:
            comparison_desc += distance_threshold_description(
                forename_col_name, "jaccard", jaccard_thresholds_forename
            )

        comparison_desc += "anything else"

        comparison_dict = {
            "comparison_description": comparison_desc,
            "comparison_levels": comparison_levels,
        }
        super().__init__(comparison_dict)
