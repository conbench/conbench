import pytest

from benchalerts.pipeline_steps.conbench import (
    BaselineRunCandidates,
    GetConbenchZComparisonForRunsStep,
    GetConbenchZComparisonStep,
)

from ..mocks import MockConbenchClient


def test_GetConbenchZComparisonForRunsStep(conbench_env):
    step = GetConbenchZComparisonForRunsStep(
        run_ids=["some_contender"],
        baseline_run_type=BaselineRunCandidates.fork_point,
        z_score_threshold=500,
        conbench_client=MockConbenchClient(),
    )
    res = step.run_step(previous_outputs={})
    assert res


def test_runs_comparison_fails_when_no_baseline(
    conbench_env, caplog: pytest.LogCaptureFixture
):
    step = GetConbenchZComparisonForRunsStep(
        run_ids=["contender_wo_base"],
        baseline_run_type=BaselineRunCandidates.fork_point,
        conbench_client=MockConbenchClient(),
    )
    res = step.run_step(previous_outputs={})
    assert res
    assert "the contender run is on the default branch" in caplog.text


def test_runs_comparison_without_commit(conbench_env, caplog: pytest.LogCaptureFixture):
    step = GetConbenchZComparisonForRunsStep(
        run_ids=["no_commit"],
        baseline_run_type=BaselineRunCandidates.latest_default,
        conbench_client=MockConbenchClient(),
    )
    res = step.run_step(previous_outputs={})
    assert res


def test_runs_comparison_skips_runs_not_found(conbench_env):
    step = GetConbenchZComparisonForRunsStep(
        run_ids=["contender_wo_base", "not_found"],
        baseline_run_type=BaselineRunCandidates.latest_default,
        conbench_client=MockConbenchClient(),
    )
    res = step.run_step(previous_outputs={})
    assert len(res.run_comparisons) == 1


def test_GetConbenchZComparisonStep(conbench_env):
    step = GetConbenchZComparisonStep(
        commit_hash="abc",
        baseline_run_type=BaselineRunCandidates.fork_point,
        z_score_threshold=500,
        conbench_client=MockConbenchClient(),
    )
    res = step.run_step(previous_outputs={})
    assert res


def test_comparison_doesnt_fail_when_no_runs(conbench_env):
    step = GetConbenchZComparisonStep(
        commit_hash="no_runs",
        baseline_run_type=BaselineRunCandidates.fork_point,
        conbench_client=MockConbenchClient(),
    )
    res = step.run_step(previous_outputs={})
    assert res


def test_comparison_warns_when_no_baseline(
    conbench_env, caplog: pytest.LogCaptureFixture
):
    step = GetConbenchZComparisonStep(
        commit_hash="no_baseline",
        baseline_run_type=BaselineRunCandidates.fork_point,
        conbench_client=MockConbenchClient(),
    )
    res = step.run_step(previous_outputs={})
    assert res
    assert "the contender run is on the default branch" in caplog.text
