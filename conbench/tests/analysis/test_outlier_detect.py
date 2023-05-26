import os
from typing import List

import pandas as pd
import pytest

"""
Note that this is executed as part of the more global conbench test suite and
therefore executes heavy fixture init/teardown logic between tests. That's not
needed conceptually, but probably OK for now. (you might get the "WARNING:
empty_db_tables() called in non-testing mode, skip" warnings in local test
execution).
"""

from conbench.outlier import remove_outliers_by_iqrdist

this_module_dirpath = os.path.dirname(os.path.abspath(__file__))


def path_to_datafile(fn: str) -> str:
    return os.path.join(this_module_dirpath, "data", fn)


def df_from_datafile(fn: str) -> pd.DataFrame:
    return pd.read_csv(path_to_datafile(fn), comment="#")


@pytest.mark.parametrize(
    "filename, expected_outliers",
    [
        ("outlier_A.csv", [269.2997, 2995.5260]),
        ("outlier_B.csv", [785.10015]),
        ("outlier_C.csv", [21.038903]),
        ("outlier_D.csv", []),
        ("outlier_E.csv", []),
    ],
)
def test_scenarios(filename: str, expected_outliers: List):
    df = df_from_datafile(filename)
    df_outliers = remove_outliers_by_iqrdist(df, "svs")
    assert list(df_outliers["svs"].values) == expected_outliers
    # print(df_outliers.index)
    # print(dfa["svs"].loc[df_outliers.index])
    # print(dfa["svs"])
    assert df["svs"].loc[df_outliers.index].isna().sum() == len((expected_outliers))
