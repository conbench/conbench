import pytest

from benchalerts.pipeline_steps.conbench import GetConbenchZComparisonStep
from benchclients import ConbenchClient

from ..mocks import MockAdapter


def test_GetConbenchZComparisonStep(conbench_env):
    step = GetConbenchZComparisonStep(
        contender_sha="abc",
        z_score_threshold=500,
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    res = step.run_step(previous_outputs={})
    assert res


def test_comparison_fails_when_no_runs(conbench_env):
    step = GetConbenchZComparisonStep(
        contender_sha="no_runs",
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    with pytest.raises(ValueError, match="runs"):
        step.run_step(previous_outputs={})


def test_comparison_warns_when_no_baseline(
    conbench_env, caplog: pytest.LogCaptureFixture
):
    step = GetConbenchZComparisonStep(
        contender_sha="no_baseline",
        conbench_client=ConbenchClient(adapter=MockAdapter()),
    )
    res = step.run_step(previous_outputs={})
    assert res
    assert "could not find a baseline run" in caplog.text
