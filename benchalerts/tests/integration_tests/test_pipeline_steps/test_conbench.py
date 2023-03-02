# Copyright (c) 2022, Voltron Data.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from benchalerts.pipeline_steps.conbench import GetConbenchZComparisonStep
from benchclients import ConbenchClient


@pytest.mark.parametrize(
    ["conbench_url", "commit", "expected_len", "expected_bip"],
    [
        # baseline is parent
        (
            "https://conbench.ursa.dev/",
            "bc7de406564fa7b2bcb9bf055cbaba31ca0ca124",
            8,
            True,
        ),
        # baseline is not parent
        (
            "https://velox-conbench.voltrondata.run",
            "2319922d288c519baa3bffe59c0bedbcb6c827cd",
            1,
            False,
        ),
        # no baseline
        (
            "https://velox-conbench.voltrondata.run",
            "b74e7045fade737e39b0f9867bc8b8b23fe00b78",
            1,
            None,
        ),
        # errors
        (
            "https://conbench.ursa.dev",
            "9fa34df27eb1445ac11b0ab0298d421b04be80f7",
            7,
            True,
        ),
    ],
)
def test_get_comparison_to_baseline(
    monkeypatch: pytest.MonkeyPatch, conbench_url, commit, expected_len, expected_bip
):
    if "ursa" in conbench_url:
        pytest.skip(
            "https://github.com/conbench/conbench/issues/745 means timeouts cause this to fail"
        )
    monkeypatch.setenv("CONBENCH_URL", conbench_url)
    cb = ConbenchClient()
    step = GetConbenchZComparisonStep(commit_hash=commit, conbench_client=cb)
    full_comparison = step.run_step(previous_outputs={})
    assert len(full_comparison.run_comparisons) == expected_len
    for run in full_comparison.run_comparisons:
        assert run.baseline_is_parent is expected_bip
        assert run.contender_link
        assert run.contender_id
        if run.compare_results:
            assert run.compare_link
            for benchmark in run.compare_results:
                assert benchmark["contender_run_id"]
