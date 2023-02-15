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
from _pytest.logging import LogCaptureFixture

from benchalerts.clients import ConbenchClient
from benchalerts.talk_to_conbench import get_comparison_to_baseline

from .mocks import MockAdapter


@pytest.fixture
def conbench(conbench_env):
    return ConbenchClient(adapter=MockAdapter())


@pytest.mark.parametrize("z_score_threshold", [None, 500])
def test_get_comparison_to_baseline(conbench, z_score_threshold):
    comparisons = get_comparison_to_baseline(conbench, "abc", z_score_threshold)
    assert isinstance(comparisons, list)
    assert len(comparisons) == 1
    assert comparisons[0].compare_link
    assert len(comparisons[0].compare_results) == 2


def test_comparison_fails_when_no_runs(conbench):
    with pytest.raises(ValueError, match="runs"):
        get_comparison_to_baseline(conbench, "no_runs")


def test_comparison_warns_when_no_baseline(conbench, caplog: LogCaptureFixture):
    comparisons = get_comparison_to_baseline(conbench, "no_baseline")
    assert isinstance(comparisons, list)
    assert len(comparisons) == 1
    assert comparisons[0].contender_link
    assert not comparisons[0].compare_link
    assert not comparisons[0].baseline_info
    assert len(comparisons[0].benchmark_results) == 2
    assert "could not find a baseline run" in caplog.text
