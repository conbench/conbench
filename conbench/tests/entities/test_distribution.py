import decimal
from copy import deepcopy

import pytest

from ...entities.distribution import (
    get_closest_ancestor,
    set_z_scores,
    update_distribution,
)
from ...tests.api import _fixtures

# --- expected data for test_update_distribution() ---
EXPECTED_STATS_ON_COMMIT_66666_LIMIT_100 = {
    "mean_mean": decimal.Decimal("3.2222221666666667"),
    "mean_sd": decimal.Decimal("1.6912410082978022"),
    "observations": 6,
}
EXPECTED_STATS_ON_COMMIT_66666_LIMIT_5 = {
    "mean_mean": decimal.Decimal("3.4666666000000000"),
    "mean_sd": decimal.Decimal("1.7683953397862708"),
    "observations": 5,
}

# This corresponds to the benchmark_results outputted from _fixtures.gen_fake_data()
EXPECTED_STATS = [
    # first commit
    {
        "mean_mean": decimal.Decimal("2.0000000000000000"),
        "mean_sd": None,
        "observations": 1,
    },
    # stayed the sameish
    {
        "mean_mean": decimal.Decimal("2.0500000000000000"),
        "mean_sd": decimal.Decimal("0.07071067811865475244"),
        "observations": 2,
    },
    # failed, so use the previous one
    {
        "mean_mean": decimal.Decimal("2.0500000000000000"),
        "mean_sd": decimal.Decimal("0.07071067811865475244"),
        "observations": 2,
    },
    # one after the failure
    {
        "mean_mean": decimal.Decimal("2.0333333333333333"),
        "mean_sd": decimal.Decimal("0.05773502691896257642"),
        "observations": 3,
    },
    # rebased onto a few unreported commits, so still 3 obs
    {
        "mean_mean": decimal.Decimal("2.0000000000000000"),
        "mean_sd": decimal.Decimal("0.10000000000000000000"),
        "observations": 3,
    },
    # default branch got better
    {
        "mean_mean": decimal.Decimal("1.7333333333333333"),
        "mean_sd": decimal.Decimal("0.55075705472861020206"),
        "observations": 3,
    },
    # rebase
    {
        "mean_mean": decimal.Decimal("1.5750000000000000"),
        "mean_sd": decimal.Decimal("0.55000000000000000000"),
        "observations": 4,
    },
    # PR gets worse
    {
        "mean_mean": decimal.Decimal("1.8600000000000000"),
        "mean_sd": decimal.Decimal("0.79561297123664342631"),
        "observations": 5,
    },
    # skip one, then three runs on the next one
    EXPECTED_STATS_ON_COMMIT_66666_LIMIT_100,
    EXPECTED_STATS_ON_COMMIT_66666_LIMIT_100,
    # different repo with error
    None,
    # commit with no branch
    None,
    # commit with no branch
    None,
    # different case
    {
        "mean_mean": decimal.Decimal("5.2000000000000000"),
        "mean_sd": None,
        "observations": 1,
    },
    # different context
    {
        "mean_mean": decimal.Decimal("5.2000000000000000"),
        "mean_sd": None,
        "observations": 1,
    },
    # different machine
    {
        "mean_mean": decimal.Decimal("5.2000000000000000"),
        "mean_sd": None,
        "observations": 1,
    },
    # different reason
    EXPECTED_STATS_ON_COMMIT_66666_LIMIT_100,
]

# Update only the distributions that change with a commit limit of 5
EXPECTED_STATS_LIMIT_5 = deepcopy(EXPECTED_STATS)
EXPECTED_STATS_LIMIT_5[6] = {
    "mean_mean": decimal.Decimal("1.4333333333333333"),
    "mean_sd": decimal.Decimal("0.57735026918962576451"),
    "observations": 3,
}
EXPECTED_STATS_LIMIT_5[7] = {
    "mean_mean": decimal.Decimal("1.7333333333333333"),
    "mean_sd": decimal.Decimal("1.0969655114602889"),
    "observations": 3,
}
EXPECTED_STATS_LIMIT_5[8] = EXPECTED_STATS_ON_COMMIT_66666_LIMIT_5
EXPECTED_STATS_LIMIT_5[9] = EXPECTED_STATS_ON_COMMIT_66666_LIMIT_5
EXPECTED_STATS_LIMIT_5[16] = EXPECTED_STATS_ON_COMMIT_66666_LIMIT_5


@pytest.mark.parametrize(
    ["commit_limit", "expected_stats"],
    [(100, EXPECTED_STATS), (5, EXPECTED_STATS_LIMIT_5)],
)
def test_update_distribution(commit_limit, expected_stats):
    _, benchmark_results = _fixtures.gen_fake_data()
    assert len(benchmark_results) == len(
        expected_stats
    ), "you should test all benchmark_results"

    for benchmark_result, some_expected_stats in zip(benchmark_results, expected_stats):
        actual_values = update_distribution(benchmark_result, commit_limit)
        if some_expected_stats is None:
            assert actual_values is None
        else:
            assert actual_values["case_id"] == benchmark_result.case_id
            assert actual_values["commit_id"] == benchmark_result.run.commit_id
            assert actual_values["context_id"] == benchmark_result.context_id
            assert actual_values["unit"] == "s"
            assert actual_values["limit"] == commit_limit
            for key, expected_value in some_expected_stats.items():
                assert actual_values[key] == expected_value


@pytest.mark.parametrize(
    ["branch_filter", "expected_shas"],
    [
        (
            None,
            [
                None,
                "11111",
                "22222",
                "aaaaa",
                "22222",
                "22222",
                "44444",
                "fffff",
                "44444",
                "44444",
                None,
                None,
                None,
                None,
                None,
                None,
                "44444",
            ],
        ),
        (
            "default",
            [
                None,
                "11111",
                "22222",
                "22222",
                "22222",
                "22222",
                "44444",
                "44444",
                "44444",
                "44444",
                None,
                None,
                None,
                None,
                None,
                None,
                "44444",
            ],
        ),
    ],
)
def test_get_closest_ancestor(branch_filter, expected_shas):
    _, benchmark_results = _fixtures.gen_fake_data()
    assert len(benchmark_results) == len(
        expected_shas
    ), "you should test all benchmark_results"

    for benchmark_result, expected_sha in zip(benchmark_results, expected_shas):
        actual_commit = get_closest_ancestor(benchmark_result, branch=branch_filter)
        if expected_sha is None:
            assert actual_commit is None
        else:
            assert expected_sha == actual_commit.sha


def test_set_z_scores():
    expected_z_scores = [
        None,
        None,
        None,
        decimal.Decimal("0.7071067811865475244016887242"),
        decimal.Decimal("2.121320343559642573205066173"),
        decimal.Decimal("13.43502884254440296363208576"),
        decimal.Decimal("1.149932312070724537187364681"),
        decimal.Decimal("-2.299864624141449255942989163"),
        decimal.Decimal("-4.720774149589126266530291312"),
        # even though same commit/hardware/case/context, z-scores get worse because they
        # are calculated on write
        decimal.Decimal("-5.204956780951700871210655559"),
        None,
        None,
        None,
        None,
        None,
        None,
        decimal.Decimal("-6.294366339755545226936030457"),
    ]
    _, benchmark_results = _fixtures.gen_fake_data()
    assert len(benchmark_results) == len(
        expected_z_scores
    ), "you should test all benchmark_results"

    set_z_scores(benchmark_results)
    for benchmark_result, expected_z_score in zip(benchmark_results, expected_z_scores):
        assert benchmark_result.z_score == expected_z_score
