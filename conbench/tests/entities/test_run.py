import pytest

from ..api import _fixtures


@pytest.mark.parametrize(
    ["give_case_and_context", "expected_baseline_run_indexes"],
    [
        (
            False,
            [None, 0, 1, 1, 1, 1, 5, 5, 5, 5, None, None, None, None, None, None, 5],
        ),
        (
            True,
            [None, 0, 1, 1, 1, 1, 5, 5, 5, 5, None, None, None, None, None, None, 5],
        ),
    ],
)
def test_get_default_baseline_run(give_case_and_context, expected_baseline_run_indexes):
    commits, benchmark_results = _fixtures.gen_fake_data()
    assert len(benchmark_results) == len(
        expected_baseline_run_indexes
    ), "you should test all benchmark_results"

    for benchmark_result, expected_baseline_run_ix in zip(
        benchmark_results, expected_baseline_run_indexes
    ):
        case_id = benchmark_result.case_id if give_case_and_context else None
        context_id = benchmark_result.context_id if give_case_and_context else None

        actual_baseline_run = benchmark_result.run.get_default_baseline_run(
            case_id=case_id, context_id=context_id
        )
        if expected_baseline_run_ix is None:
            assert actual_baseline_run is None
        else:
            assert (
                actual_baseline_run == benchmark_results[expected_baseline_run_ix].run
            )

    # create one more nightly on 44444 and hope that we pick it up in the last test case
    new_one = _fixtures.benchmark_result(
        name=benchmark_result.case.name,
        results=[1, 2, 3],
        reason="nightly",
        commit=commits["44444"],
    )
    assert (
        benchmark_result.run.get_default_baseline_run(
            case_id=case_id, context_id=context_id
        )
        == new_one.run
    )
