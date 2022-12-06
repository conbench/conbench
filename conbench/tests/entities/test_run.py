from ..api import _fixtures


def test_get_baseline_run():
    commits, benchmark_results = _fixtures.gen_fake_data()
    expected_baseline_runs = [
        None,
        benchmark_results[0].run,
        benchmark_results[1].run,
        benchmark_results[2].run,
        benchmark_results[1].run,
        benchmark_results[1].run,
        benchmark_results[5].run,
        benchmark_results[6].run,
        benchmark_results[5].run,
        benchmark_results[5].run,
        None,
        None,
        None,
        None,
        None,
        None,
        # despite this being a nightly, will find a commit because there are no other nightlies
        benchmark_results[5].run,
    ]
    assert len(benchmark_results) == len(
        expected_baseline_runs
    ), "you should test all benchmark_results"

    for benchmark_result, expected_baseline_run in zip(
        benchmark_results, expected_baseline_runs
    ):
        actual_baseline_run = benchmark_result.run.get_baseline_run()
        assert expected_baseline_run == actual_baseline_run

    # create one more nightly on 44444 and hope that we pick it up in the last test case
    new_one = _fixtures.benchmark_result(
        name=benchmark_results[-1].case.name,
        results=[1, 2, 3],
        reason="nightly",
        commit=commits["44444"],
    )
    assert benchmark_results[-1].run.get_baseline_run() == new_one.run
