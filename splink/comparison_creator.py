from abc import ABC, abstractmethod
from typing import List, Union, final

from .column_expression import ColumnExpression
from .comparison import Comparison
from .comparison_level_creator import ComparisonLevelCreator
from .exceptions import SplinkException
from .misc import ensure_is_list


class ComparisonCreator(ABC):
    def __init__(
        self,
        col_name_or_names: Union[
            List[Union[str, ColumnExpression]], Union[str, ColumnExpression]
    ):
        """
        Class to author Comparisons
        Args:
            col_name_or_names (str, ColumnExpression): Input column name(s).
                Can be a single item or a list.
        """
        if col_name_or_names is None:
            cols = []
        else:
            # use list rather than iterable so we don't decompose strings
            cols = ensure_is_list(col_name_or_names)
        # TODO: would this be nicer as a dict?
        self.col_expressions = list(
            map(
                ColumnExpression.instantiate_if_str,
                cols,
            )
        )

    # many ComparisonCreators have a single column expression, so provide a
    # convenience property for this case. Error if there are none or many
    @property
    def col_expression(self) -> ColumnExpression:
        num_cols = len(self.col_expressions)
        if num_cols > 1:
            raise SplinkException(
                "Cannot get `ComparisonLevelCreator.col_expression` when "
                f"`.col_expressions` has more than one element: {type(self)}"
            )
        if num_cols == 0:
            raise SplinkException(
                "Cannot get `ComparisonLevelCreator.col_expression` when "
                f"`.col_expressions` has no elements: {type(self)}"
            )
        return self.col_expressions[0]

    # TODO: property?
    @abstractmethod
    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        pass

    @final
    def get_configured_comparison_levels(self) -> List[ComparisonLevelCreator]:
        # furnish comparison levels with m and u probabilities as needed
        comparison_levels = self.create_comparison_levels()

        if self.m_probabilities:
            m_values = self.m_probabilities.copy()
            comparison_levels = [
                cl.configure(
                    m_probability=m_values.pop(0) if not cl.is_null_level else None,
                )
                for cl in comparison_levels
            ]
        if self.u_probabilities:
            u_values = self.u_probabilities.copy()
            comparison_levels = [
                cl.configure(
                    u_probability=u_values.pop(0) if not cl.is_null_level else None,
                )
                for cl in comparison_levels
            ]
        return comparison_levels

    @final
    @property
    def num_levels(self) -> int:
        return len(self.create_comparison_levels())

    @final
    @property
    def num_non_null_levels(self) -> int:
        return len(
            [cl for cl in self.create_comparison_levels() if not cl.is_null_level]
        )

    @abstractmethod
    def create_description(self) -> str:
        pass

    @abstractmethod
    def create_output_column_name(self) -> str:
        pass

    @final
    def get_comparison(self, sql_dialect_str: str) -> Comparison:
        """sql_dialect_str is a string to make this method easier to use
        for the end user - otherwise they'd need to import a SplinkDialect"""
        return Comparison(self.create_comparison_dict(sql_dialect_str))

    @final
    def create_comparison_dict(self, sql_dialect_str: str) -> dict:
        level_dict = {
            "comparison_description": self.create_description(),
            "output_column_name": self.create_output_column_name(),
            "comparison_levels": [
                cl.get_comparison_level(sql_dialect_str)
                for cl in self.get_configured_comparison_levels()
            ],
        }

        return level_dict

    @final
    def configure(
        self,
        *,
        m_probabilities: list[float] = None,
        u_probabilities: list[float] = None,
    ) -> "ComparisonCreator":
        """
        Configure the comparison creator with m and u probabilities. The first
        element in the list corresponds to the first comparison level, usually
        an exact match level. Subsequent elements correspond comparison to
        levels in sequential order, through to the last element which is usually
        the 'ELSE' level.

        Example:
            cc = LevenshteinAtThresholds("name", 2)
            cc.configure(
                m_probabilities=[0.9, 0.08, 0.02],
                u_probabilities=[0.01, 0.05, 0.94]
                # probabilities for exact match level, levenshtein <= 2, and else
                # in that order
            )
        Args:
            m_probabilities (list, optional): List of m probabilities
            u_probabilities (list, optional): List of u probabilities
        """
        self.m_probabilities = m_probabilities
        self.u_probabilities = u_probabilities
        return self

    @final
    @property
    def m_probabilities(self):
        return getattr(self, "_m_probabilities", None)

    @final
    @m_probabilities.setter
    def m_probabilities(self, m_probabilities: list[float]):
        if m_probabilities:
            num_probs_supplied = len(m_probabilities)
            num_non_null_levels = self.num_non_null_levels
            if num_probs_supplied != self.num_non_null_levels:
                raise ValueError(
                    f"Comparison has {num_non_null_levels} non-null levels, "
                    f"but received {num_probs_supplied} values for m_probabilities. "
                    "These numbers must be the same."
                )
            self._m_probabilities = m_probabilities

    @final
    @property
    def u_probabilities(self):
        return getattr(self, "_u_probabilities", None)

    @final
    @u_probabilities.setter
    def u_probabilities(self, u_probabilities: list[float]):
        if u_probabilities:
            num_probs_supplied = len(u_probabilities)
            num_non_null_levels = self.num_non_null_levels
            if num_probs_supplied != self.num_non_null_levels:
                raise ValueError(
                    f"Comparison has {num_non_null_levels} non-null levels, "
                    f"but received {num_probs_supplied} values for u_probabilities. "
                    "These numbers must be the same."
                )
            self._u_probabilities = u_probabilities

    def __repr__(self) -> str:
        return (
            f"Comparison generator for {self.create_description()}. "
            "Call .get_comparison(sql_dialect_str) to instantiate "
            "a Comparison"
        )
