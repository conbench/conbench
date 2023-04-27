import pytest
from benchclients.conbench import LegacyConbenchClient

from benchalerts.pipeline_steps.conbench import (
    BaselineRunCandidates,
    GetConbenchZComparisonForRunsStep,
    GetConbenchZComparisonStep,
)

from ..mocks import MockAdapter

ConbenchClient = LegacyConbenchClient


def test_GetConbenchZComparisonForRunsStep(conbench_env):
    step = GetConbenchZComparisonForRunsStep(
        run_ids=["some_contender"],
        baseline_run_type=BaselineRunCandidates.fork_point,
        z_score_threshold=500,
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    res = step.run_step(previous_outputs={})
    assert res


def test_runs_comparison_fails_when_no_baseline(
    conbench_env, caplog: pytest.LogCaptureFixture
):
    step = GetConbenchZComparisonForRunsStep(
        run_ids=["contender_wo_base"],
        baseline_run_type=BaselineRunCandidates.fork_point,
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    res = step.run_step(previous_outputs={})
    assert res
    assert "the contender run is on the default branch" in caplog.text


def test_GetConbenchZComparisonStep(conbench_env):
    step = GetConbenchZComparisonStep(
        commit_hash="abc",
        baseline_run_type=BaselineRunCandidates.fork_point,
        z_score_threshold=500,
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    res = step.run_step(previous_outputs={})
    assert res


def test_comparison_fails_when_no_runs(conbench_env):
    step = GetConbenchZComparisonStep(
        commit_hash="no_runs",
        baseline_run_type=BaselineRunCandidates.fork_point,
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    with pytest.raises(ValueError, match="runs"):
        step.run_step(previous_outputs={})


def test_comparison_warns_when_no_baseline(
    conbench_env, caplog: pytest.LogCaptureFixture
):
    step = GetConbenchZComparisonStep(
        commit_hash="no_baseline",
        baseline_run_type=BaselineRunCandidates.fork_point,
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    res = step.run_step(previous_outputs={})
    assert res
    assert "the contender run is on the default branch" in caplog.text
