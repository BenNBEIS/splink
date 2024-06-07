from __future__ import annotations

import logging
import multiprocessing
from copy import deepcopy
from typing import TYPE_CHECKING, List

from splink.internals.blocking import block_using_rules_sqls, blocking_rule_to_obj
from splink.internals.comparison_vector_values import (
    compute_comparison_vector_values_sql,
)
from splink.internals.m_u_records_to_parameters import (
    append_u_probability_to_comparison_level_trained_probabilities,
    m_u_records_to_lookup_dict,
)
from splink.internals.pipeline import CTEPipeline
from splink.internals.vertically_concatenate import (
    enqueue_df_concat,
    split_df_concat_with_tf_into_two_tables_sqls,
)

from .expectation_maximisation import (
    compute_new_parameters_sql,
    compute_proportions_for_new_parameters,
)

# https://stackoverflow.com/questions/39740632/python-type-hinting-without-cyclic-imports
if TYPE_CHECKING:
    from splink.internals.linker import Linker

logger = logging.getLogger(__name__)


def _rows_needed_for_n_pairs(n_pairs):
    # Number of pairs generated by cartesian product is
    # p(r) = r(r-1)/2, where r is input rows
    # Solve this for r
    # https://www.wolframalpha.com/input?i=Solve%5Bp%3Dr+*+%28r+-+1%29+%2F+2%2C+r%5D
    sample_rows = 0.5 * ((8 * n_pairs + 1) ** 0.5 + 1)
    return sample_rows


def _proportion_sample_size_link_only(
    row_counts_individual_dfs: List[int], max_pairs: float
) -> tuple[float, float]:
    # total valid links is sum of pairwise product of individual row counts
    # i.e. if frame_counts are [a, b, c, d, ...],
    # total_links = a*b + a*c + a*d + ... + b*c + b*d + ... + c*d + ...
    total_links = (
        sum(row_counts_individual_dfs) ** 2
        - sum([count**2 for count in row_counts_individual_dfs])
    ) / 2
    total_nodes = sum(row_counts_individual_dfs)

    # if we scale each frame by a proportion total_links scales with the square
    # i.e. (our target) max_pairs == proportion^2 * total_links
    proportion = (max_pairs / total_links) ** 0.5
    # sample size is for df_concat_with_tf, i.e. proportion of the total nodes
    sample_size = proportion * total_nodes
    return proportion, sample_size


def estimate_u_values(linker: Linker, max_pairs: float, seed: int = None) -> None:
    logger.info("----- Estimating u probabilities using random sampling -----")
    pipeline = CTEPipeline()

    pipeline = enqueue_df_concat(linker, pipeline)

    original_settings_obj = linker._settings_obj

    training_linker: Linker = deepcopy(linker)

    settings_obj = training_linker._settings_obj
    settings_obj._retain_matching_columns = False
    settings_obj._retain_intermediate_calculation_columns = False

    db_api = training_linker.db_api

    for cc in settings_obj.comparisons:
        for cl in cc.comparison_levels:
            # TODO: ComparisonLevel: manage access
            cl._tf_adjustment_column = None

    if settings_obj._link_type in ["dedupe_only", "link_and_dedupe"]:
        sql = """
        select count(*) as count
        from __splink__df_concat
        """

        pipeline.enqueue_sql(sql, "__splink__df_concat_count")
        count_dataframe = db_api.sql_pipeline_to_splink_dataframe(pipeline)

        result = count_dataframe.as_record_dict()
        count_dataframe.drop_table_from_database_and_remove_from_cache()
        total_nodes = result[0]["count"]
        sample_size = _rows_needed_for_n_pairs(max_pairs)
        proportion = sample_size / total_nodes

    if settings_obj._link_type == "link_only":
        sql = """
        select count(source_dataset) as count
        from __splink__df_concat
        group by source_dataset
        """
        pipeline.enqueue_sql(sql, "__splink__df_concat_count")
        counts_dataframe = db_api.sql_pipeline_to_splink_dataframe(pipeline)
        result = counts_dataframe.as_record_dict()
        counts_dataframe.drop_table_from_database_and_remove_from_cache()
        frame_counts = [res["count"] for res in result]

        proportion, sample_size = _proportion_sample_size_link_only(
            frame_counts, max_pairs
        )

        total_nodes = sum(frame_counts)

    if proportion >= 1.0:
        proportion = 1.0

    if sample_size > total_nodes:
        sample_size = total_nodes

    pipeline = CTEPipeline()
    pipeline = enqueue_df_concat(training_linker, pipeline)

    sql = f"""
    select *
    from __splink__df_concat
    {training_linker._random_sample_sql(proportion, sample_size, seed)}
    """

    pipeline.enqueue_sql(sql, "__splink__df_concat_sample")
    df_sample = db_api.sql_pipeline_to_splink_dataframe(pipeline)

    pipeline = CTEPipeline(input_dataframes=[df_sample])

    if linker._sql_dialect == "duckdb" and max_pairs > 1e4:
        br = blocking_rule_to_obj(
            {
                "blocking_rule": "1=1",
                "salting_partitions": multiprocessing.cpu_count(),
            }
        )
        settings_obj._blocking_rules_to_generate_predictions = [br]
    else:
        settings_obj._blocking_rules_to_generate_predictions = []

    input_tablename_sample_l = "__splink__df_concat_sample"
    input_tablename_sample_r = "__splink__df_concat_sample"

    if (
        len(linker._input_tables_dict) == 2
        and linker._settings_obj._link_type == "link_only"
    ):
        sqls = split_df_concat_with_tf_into_two_tables_sqls(
            "__splink__df_concat",
            linker._settings_obj.column_info_settings.source_dataset_column_name,
            sample_switch=True,
        )
        input_tablename_sample_l = "__splink__df_concat_sample_left"
        input_tablename_sample_r = "__splink__df_concat_sample_right"

        pipeline.enqueue_list_of_sqls(sqls)

    sql_infos = block_using_rules_sqls(
        input_tablename_l=input_tablename_sample_l,
        input_tablename_r=input_tablename_sample_r,
        blocking_rules=settings_obj._blocking_rules_to_generate_predictions,
        link_type=linker._settings_obj._link_type,
        columns_to_select_sql=", ".join(settings_obj._columns_to_select_for_blocking),
        source_dataset_input_column=settings_obj.column_info_settings.source_dataset_input_column,
        unique_id_input_column=settings_obj.column_info_settings.unique_id_input_column,
    )
    pipeline.enqueue_list_of_sqls(sql_infos)

    # repartition after blocking only exists on the SparkLinker
    repartition_after_blocking = getattr(linker, "repartition_after_blocking", False)
    if repartition_after_blocking:
        pipeline = pipeline.break_lineage(db_api)

    sql = compute_comparison_vector_values_sql(
        settings_obj._columns_to_select_for_comparison_vector_values
    )

    pipeline.enqueue_sql(sql, "__splink__df_comparison_vectors")

    sql = """
    select *, cast(0.0 as float8) as match_probability
    from __splink__df_comparison_vectors
    """

    pipeline.enqueue_sql(sql, "__splink__df_predict")

    sql = compute_new_parameters_sql(
        estimate_without_term_frequencies=False,
        comparisons=settings_obj.comparisons,
    )

    pipeline.enqueue_sql(sql, "__splink__m_u_counts")
    df_params = db_api.sql_pipeline_to_splink_dataframe(pipeline)

    param_records = df_params.as_pandas_dataframe()
    param_records = compute_proportions_for_new_parameters(param_records)
    df_params.drop_table_from_database_and_remove_from_cache()
    df_sample.drop_table_from_database_and_remove_from_cache()

    m_u_records = [
        r
        for r in param_records
        if r["output_column_name"] != "_probability_two_random_records_match"
    ]

    m_u_records_lookup = m_u_records_to_lookup_dict(m_u_records)

    for c in original_settings_obj.comparisons:
        for cl in c._comparison_levels_excluding_null:
            append_u_probability_to_comparison_level_trained_probabilities(
                cl,
                m_u_records_lookup,
                c.output_column_name,
                "estimate u by random sampling",
            )

    logger.info("\nEstimated u probabilities using random sampling")
