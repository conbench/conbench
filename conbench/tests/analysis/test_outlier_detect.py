import pandas as pd

from conbench.outlier import remove_outliers_by_iqrdist


def test_senario_A():
    dfa = pd.read_csv("data/outlier_A.csv", comment="#")

    df_outliers = remove_outliers_by_iqrdist(dfa, "svs")
    assert list(df_outliers["svs"].values) == [269.2997, 2995.5260]
    # print(df_outliers.index)
    # print(dfa["svs"].loc[df_outliers.index])
    # print(dfa["svs"])
    assert dfa["svs"].loc[df_outliers.index].isna().sum() == 2


def test_senario_B():
    df = pd.read_csv("data/outlier_B.csv", comment="#")
    df_outliers = remove_outliers_by_iqrdist(df, "svs")
    assert list(df_outliers["svs"].values) == [785.10015]
    assert df["svs"].loc[df_outliers.index].isna().sum() == 1


def test_senario_C():
    df = pd.read_csv("data/outlier_C.csv", comment="#")
    df_outliers = remove_outliers_by_iqrdist(df, "svs")
    assert list(df_outliers["svs"].values) == [21.038903]
    assert df["svs"].loc[df_outliers.index].isna().sum() == 1


def test_senario_D():
    df = pd.read_csv("data/outlier_D.csv", comment="#")
    df_outliers = remove_outliers_by_iqrdist(df, "svs")
    assert list(df_outliers["svs"].values) == []
    assert df["svs"].loc[df_outliers.index].isna().sum() == 0
