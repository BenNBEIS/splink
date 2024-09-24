# This sql code for solving connected components takes inspiration
# from the following paper: https://arxiv.org/pdf/1802.09478.pdf

# While we haven't been able to implement the solution presented
# by the paper - due to SQL backend restrictions with UDFs, -
# we have been able to use the paper to further our understanding
# of the problem and come to a working solution.

# See also https://github.com/RobinL/clustering_in_sql

from __future__ import annotations

import logging
import time
from typing import Optional

from splink.internals.database_api import DatabaseAPISubClass
from splink.internals.pipeline import CTEPipeline
from splink.internals.splink_dataframe import SplinkDataFrame

logger = logging.getLogger(__name__)


def _cc_create_unique_id_cols():
    pass


def _cc_generate_neighbours_representation() -> str:
    """SQL to generate all the 'neighbours' of each input node.

    The 'neighbour' of a node is any other node that is connected to the original node
    within the graph.  'Connected' means that at the threshold match probability,
    the nodes are considered to be a match (i.e. the nodes are estimated to
    be same entity)

    This table differs to the edges table in two respects:
    1.  Unlike the edges table, it's not guaranteed that the node (left hand side)
        has a lower id than the neighbour.  That is, the left column (node_id) contains
        all the nodes, not just the ones with a higher id on the right hand side
    2. The table contains all nodes, even those with no edges (these are represented)
        as a 'self link' i.e. ID1 -> ID1, ensuring they are present in the final
        clusters table.
    """

    sql = """
    select n.node_id,
        e_l.node_id_r as neighbour
    from nodes as n

    left join __splink__edges as e_l
        on n.node_id = e_l.node_id_l

    UNION

    select n.node_id,
        coalesce(e_r.node_id_l, n.node_id) as neighbour
    from nodes as n

    left join __splink__edges as e_r
        on n.node_id = e_r.node_id_r
    """

    return sql


def _cc_generate_initial_representatives_table() -> str:
    """SQL to generate our initial "representatives" table.

    The 'representative' column will eventually become the cluster ID.

    As outlined in the paper quoted at the top:

    '...begin by choosing for each vertex (node) a representatative by picking the
    vertex (node) with the minimum id amongst itself and its neighbours'.

    e.g. node ids 1, 2 and 3 may all have representative 2, indicating
    they are a cluster.

    This is done initially by grouping on our neighbours table
    and finding the minimum neighbour for each node.
    """

    sql = """
    select
        neighbours.node_id,
        min(neighbour) as representative

    from __splink__df_neighbours as neighbours
    group by node_id
    order by node_id
    """

    return sql


def _cc_update_neighbours_first_iter() -> str:
    """SQL to update our neighbours table - first iteration only.

    Takes our initial neighbours table, join on the representatives table
    and recalculates the mimumum representative for each node.

    This works by joining on the current known representative for each node's
    neighbours.

    i.e. rather than looking at a node's minimum representative, we look at the node's
    neighbour's minimum representative.

    So, if we know that B is represented by A (B -> A) and C is represented by B
    (C -> B), then we can join on B to conclude that (C -> A).
    """

    sql = """
    select
        neighbours.node_id,
        min(representatives.representative) as representative

    from __splink__df_neighbours as neighbours
    left join representatives
    on neighbours.neighbour = representatives.node_id
        group by neighbours.node_id
        order by neighbours.node_id
    """

    return sql


def _cc_update_representatives_first_iter() -> str:
    """SQL to update our representatives table - first iteration only.

    From here, standardised code can be used inside a while loop,
    as the representatives table no longer needs generating.

    This is only used for the first iteration as we

    In this SQL, we also generate "rep_match", which is a boolean
    that indicates whether the current representative differs
    from the previous representative.

    This value is used extensively to speed up our while loop and as
    an exit condition.
    """

    sql = """
    select
        n.node_id,
        n.representative,
        n.representative <> repr.representative as rep_match
    from neighbours_first_iter as n
    inner join representatives as repr
    on n.node_id = repr.node_id
    """

    return sql


def _cc_generate_representatives_loop_cond(
    prev_representatives: str,
) -> str:
    """SQL for Connected components main loop.

    Takes our core neighbours table (this is constant), and
    joins on the current representatives table from the
    previous iteration by joining on information about each node's
    neighbours representatives.

    So, reusing the same summary logic mentioned above, if we know that B
    is represented by A (B -> A) and C is represented by B (C -> B),
    then we can join (B -> A) onto (C -> B) to conclude that (C -> A).

    Doing this iteratively eventually allows us to climb up the ladder through
    all of our neighbours' representatives to a solution.

    The key difference between this function and 'cc_update_neighbours_first_iter',
    is the usage of 'rep_match'.

    The logic behind 'rep_match' is summarised in 'cc_update_representatives_first_iter'
    and it can be used here to reduce our neighbours table to only those nodes that need
    updating.
    """

    sql = f"""
    select

    source.node_id,
    min(source.representative) as representative

    from
    (

        select

            neighbours.node_id,
            repr_neighbour.representative as representative

        from __splink__df_neighbours as neighbours

        inner join {prev_representatives} as repr_neighbour
        on neighbours.neighbour = repr_neighbour.node_id

        where
            repr_neighbour.rep_match = True

        UNION ALL

        select

            node_id,
            representative

        from {prev_representatives}
        where
            {prev_representatives}.rep_match = False

    ) AS source
    group by source.node_id
        """

    return sql


def _cc_update_representatives_loop_cond(
    prev_representatives: str,
) -> str:
    """SQL to update our representatives table - while loop condition.

    Reorganises our representatives output generated in
    cc_generate_representatives_loop_cond() and isolates 'rep_match',
    which indicates whether all representatives have 'settled' (i.e.
    no change from previous iteration).
    """

    sql = f"""
    select

        r.node_id,
        r.representative,
        r.representative <> repr.representative as rep_match

    from r

    left join {prev_representatives} as repr
    on r.node_id = repr.node_id
        """

    return sql


def _cc_assess_exit_condition(representatives_name: str) -> str:
    """SQL exit condition for our Connected Components algorithm.

    Where 'rep_match' (summarised in 'cc_update_representatives_first_iter')
    it indicates that some nodes still require updating and have not yet
    settled.
    """

    sql = f"""
            select count(*) as count
            from {representatives_name}
            where rep_match
        """

    return sql


def solve_connected_components(
    nodes_table: SplinkDataFrame,
    edges_table: SplinkDataFrame,
    node_id_column_name: str,
    edge_id_column_name_left: str,
    edge_id_column_name_right: str,
    db_api: DatabaseAPISubClass,
    threshold_match_probability: Optional[float],
) -> SplinkDataFrame:
    """Connected Components main algorithm.

    This function helps cluster your linked (or deduped) records
    into single groups, which can then be more easily visualised.

    Args:
        linker:
            Splink linker object. For more, see splink.linker.

        edges_table (SplinkDataFrame):
            Splink dataframe containing our edges dataframe to be connected.



    Returns:
        SplinkDataFrame: A dataframe containing the connected components list
        for your link or dedupe job.

    """

    pipeline = CTEPipeline([edges_table, nodes_table])

    match_prob_expr = f"where match_probability >= {threshold_match_probability}"
    if threshold_match_probability is None:
        match_prob_expr = ""

    sql = f"""
    select
        {edge_id_column_name_left} as node_id_l,
        {edge_id_column_name_right} as node_id_r
    from {edges_table.physical_name}
    {match_prob_expr}

    UNION

    select
    {node_id_column_name} as node_id_l,
    {node_id_column_name} as node_id_r
    from {nodes_table.physical_name}
    """
    pipeline.enqueue_sql(sql, "__splink__edges")
    edges = db_api.sql_pipeline_to_splink_dataframe(pipeline)

    pipeline = CTEPipeline([edges])

    sql = f"select {node_id_column_name} as node_id from {nodes_table.physical_name}"

    pipeline.enqueue_sql(sql, "nodes")

    sql = _cc_generate_neighbours_representation()
    pipeline.enqueue_sql(sql, "__splink__df_neighbours")
    neighbours = db_api.sql_pipeline_to_splink_dataframe(pipeline)

    # Create our initial representatives table
    pipeline = CTEPipeline([neighbours])
    sql = _cc_generate_initial_representatives_table()
    pipeline.enqueue_sql(sql, "representatives")
    sql = _cc_update_neighbours_first_iter()
    pipeline.enqueue_sql(sql, "neighbours_first_iter")
    sql = _cc_update_representatives_first_iter()
    # Execute if we have no batching, otherwise add it to our batched process
    pipeline.enqueue_sql(sql, "__splink__df_representatives")

    representatives = db_api.sql_pipeline_to_splink_dataframe(pipeline)
    # c = representatives.as_duckdbpyrelation().count("*").fetchone()[0]
    # print(f"representatives: {c:,.0f}")
    # print(representatives.as_duckdbpyrelation().show())

    prev_representatives_table = representatives

    # Loop while our representative table still has unsettled nodes
    iteration, root_rows_count = 0, 1

    converged_repr_tables = []
    while root_rows_count > 0:
        start_time = time.time()
        iteration += 1
        # print(f"Starting iteration {iteration}")

        # Loop summary:

        # 1. Update our neighbours table.
        # 2. Join on the representatives table from the previous iteration
        #    to create the "rep_match" column.
        # 3. Assess if our exit condition has been met.

        # Generates our representatives table for the next iteration
        # by joining our previous tables onto our neighbours table.
        # print("prev_representatives_table")
        # print(prev_representatives_table.as_duckdbpyrelation())

        pipeline = CTEPipeline([neighbours])
        sql = _cc_generate_representatives_loop_cond(
            prev_representatives_table.physical_name,
        )
        pipeline.enqueue_sql(sql, "r")
        # Update our rep_match column in the representatives table.
        sql = _cc_update_representatives_loop_cond(
            prev_representatives_table.physical_name
        )

        repr_name = f"__splink__df_representatives_{iteration}"

        pipeline.enqueue_sql(
            sql,
            repr_name,
        )

        representatives = db_api.sql_pipeline_to_splink_dataframe(pipeline)

        # print("representatives")
        # print(representatives.as_duckdbpyrelation())

        # Report stable clusters - those where the cluster size
        # has not changed (or become null) since the last iteration
        pipeline = CTEPipeline([neighbours, representatives])
        sql = f"""
        select
            r.representative,
            list_sort(list_distinct(array_agg(r.node_id order by r.node_id)))
                as distinct_node_ids,
            list_sort(list_distinct(array_agg(neighbours.neighbour order by r.node_id)))
                as distinct_neighbours

        from {representatives.templated_name} as r
        left join __splink__df_neighbours as neighbours
        on r.node_id = neighbours.node_id

        group by r.representative
        """
        pipeline.enqueue_sql(sql, "cluster_composition_current")

        sql = """
        SELECT
            representative,
            distinct_node_ids
        FROM cluster_composition_current
        WHERE distinct_node_ids = distinct_neighbours
        """
        pipeline.enqueue_sql(sql, "stable_clusters")

        # print("stable_clusters")
        # print(stable_clusters.as_duckdbpyrelation())

        # Grab stable clusters and save to table

        sql = f"""
        select
            *
        from {representatives.physical_name}
        where representative in (select representative from stable_clusters)
        """
        pipeline.enqueue_sql(sql, "__splink__representatives_stable")
        representatives_stable = db_api.sql_pipeline_to_splink_dataframe(pipeline)

        # print("found stable representatives for removal")
        # representatives_stable.as_duckdbpyrelation().show()
        converged_repr_tables.append(representatives_stable)

        # print("representatives_stable")
        # print(representatives_stable.as_duckdbpyrelation())

        # Filter out the stable cluster and recalculate the representatives table
        # to drop the stable nodes
        pipeline = CTEPipeline([representatives_stable])
        sql = f"""
        select
            *
        from {representatives.physical_name}
        where representative not in
        (select representative from __splink__representatives_stable)
        """
        pipeline.enqueue_sql(sql, "representatives_thinned")
        representatives_thinned = db_api.sql_pipeline_to_splink_dataframe(pipeline)

        # print("representatives_thinned")
        # print(representatives_thinned.as_duckdbpyrelation())

        pipeline = CTEPipeline()
        # Update table reference
        prev_representatives_table.drop_table_from_database_and_remove_from_cache()
        prev_representatives_table = representatives_thinned

        # Check if our exit condition has been met...
        sql = _cc_assess_exit_condition(representatives_thinned.physical_name)

        pipeline.enqueue_sql(sql, "__splink__df_root_rows")

        root_rows_df = db_api.sql_pipeline_to_splink_dataframe(
            pipeline, use_cache=False
        )

        root_rows = root_rows_df.as_record_dict()
        root_rows_df.drop_table_from_database_and_remove_from_cache()
        root_rows_count = root_rows[0]["count"]
        logger.info(
            f"Completed iteration {iteration}, root rows count {root_rows_count}"
        )
        end_time = time.time()
        logger.log(15, f"    Iteration time: {end_time - start_time} seconds")

    pipeline = CTEPipeline()

    sql = " UNION ALL ".join(
        [f"select * from {t.physical_name}" for t in converged_repr_tables]
    )

    pipeline.enqueue_sql(sql, "__splink__clustering_output")

    sql = f"""
    select representative as cluster_id,
    node_id as {node_id_column_name}
    from __splink__clustering_output
    order by cluster_id, node_id
    """

    pipeline.enqueue_sql(sql, "__splink__clustering_output_final")

    final = db_api.sql_pipeline_to_splink_dataframe(pipeline)

    return final
