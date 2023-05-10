# To test: levels, comparisons, different regex syntax
# Start with duckDB and then test for spark, Athena? if the SQL changes, SQLite?
# if spark linker then should give value error if syntax is wrong

### LEVEL TEST
import pandas as pd
import pytest
from splink.duckdb.duckdb_linker import DuckDBLinker
from splink.spark.spark_linker import SparkLinker
import splink.duckdb.duckdb_comparison_level_library as clld
import splink.spark.spark_comparison_level_library as clls


df = pd.DataFrame(
    [
        {
            "unique_id": 1,
            "first_name": "Andy",
            "last_name": "Williams",
            "postcode": "SE1P 0NY",
        },
        {
            "unique_id": 2,
            "first_name": "Andy's twin",
            "last_name": "Williams",
            "postcode": "SE1P 0NY",
        },
        {
            "unique_id": 3,
            "first_name": "Tom",
            "last_name": "Williams",
            "postcode": "SE1P 0PZ",
        },
        {
            "unique_id": 4,
            "first_name": "Robin",
            "last_name": "Williams",
            "postcode": "SE1P 4UY",
        },
        {
            "unique_id": 5,
            "first_name": "Sam",
            "last_name": "Rosston",
            "postcode": "SE2 7TR",
        },
        {
            "unique_id": 6,
            "first_name": "Ross",
            "last_name": "Samson",
            "postcode": "SW15 8UY",
        },
    ]
)


def postcode_levels(cll):
    return {
        "output_column_name": "postcode",
        "comparison_levels": [
            cll.exact_match_level(
                "postcode", regex_extract="^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9]"
            ),
            cll.levenshtein_level(
                "postcode",
                distance_threshold=1,
                regex_extract="^[A-Z]{1,2}[0-9][A-Z0-9]?",
            ),
            cll.jaro_level(
                "postcode", distance_threshold=1, regex_extract="^[A-Z]{1,2}"
            ),
            cll.else_level(),
        ],
    }


# update jaccard
def name_levels(cll):
    return {
        "output_column_name": "name",
        "comparison_levels": [
            cll.jaro_winkler_level(
                "first_name", distance_threshold=1, regex_extract="^[A-Z]{1,4}"
            ),
            # cll.jaccard_level("first_name", distance_threshold=1.0, regex_extract="[A-Z]"),
            cll.columns_reversed_level(
                "first_name", "last_name", regex_extract="[A-Z]{1,3}"
            ),
            cll.else_level(),
        ],
    }


record_pairs_gamma_postcode = {
    # 4: [(1, 2)],
    3: [(1, 2), (1, 3), (2, 3)],
    2: [(1, 4), (2, 4), (3, 4)],
    1: [(1, 5), (2, 5), (3, 5), (4, 5)],
}

record_pairs_gamma_name = {
    # 4: [(1, 2)],
    # 3: [(1, 3), (2, 3)],
    2: [(1, 2), (4, 6)],
    1: [(5, 6)],
}


@pytest.mark.parametrize(
    ("Linker", "df", "level_set", "record_pairs_gamma"),
    [
        pytest.param(
            DuckDBLinker,
            df,
            postcode_levels(clld),
            record_pairs_gamma_postcode,
            id="DuckDB postcode regex levels test",
        ),
        pytest.param(
            DuckDBLinker,
            df,
            name_levels(clld),
            record_pairs_gamma_name,
            id="DuckDB name regex levels test",
        ),
        pytest.param(
            SparkLinker,
            df,
            postcode_levels(clls),
            record_pairs_gamma_postcode,
            id="Spark postcode regex levels test",
        ),
        pytest.param(
            SparkLinker,
            df,
            name_levels(clls),
            record_pairs_gamma_name,
            id="Spark name regex levels test",
        ),
    ],
)
def test_regex(spark, Linker, df, level_set, record_pairs_gamma):

    # Generate settings
    settings = {
        "link_type": "dedupe_only",
        "comparisons": [level_set],
    }

    comparison_name = level_set["output_column_name"]

    if Linker == SparkLinker:
        df = spark.createDataFrame(df)
        df.persist()
    linker = Linker(df, settings)

    linker_output = linker.predict().as_pandas_dataframe()

    for gamma, id_pairs in record_pairs_gamma.items():
        for left, right in id_pairs:
            print(f"Checking IDs: {left}, {right}")
            assert (
                linker_output.loc[
                    (linker_output.unique_id_l == left)
                    & (linker_output.unique_id_r == right)
                ][f"gamma_{comparison_name}"].values[0]
                == gamma
            )


# TEST REGEX SYNTAX
# Check spark linker errors if bad regex syntax
# Test they don't break for other random regex syntax, blank string, null
# Just for exact match level
# test \ and single {}


### TEST COMPARISONS - as above
