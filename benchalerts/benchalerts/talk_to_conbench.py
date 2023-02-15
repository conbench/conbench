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

from dataclasses import dataclass
from typing import List, Optional

from .clients import ConbenchClient
from .log import fatal_and_log, log


@dataclass
class RunComparison:
    """Track info about a comparison between a contender run and its baseline. Used for
    outputting information from get_comparison_to_baseline().

    Parameters
    ----------
    contender_info
        The dict returned from Conbench when hitting /runs/{contender_run_id}. Contains
        info about the run's ID, commit, errors, links, etc.
    baseline_info
        The dict returned from Conbench when hitting /runs/{baseline_run_id}, if a
        baseline run exists for this contender run. Contains info about the run's ID,
        commit, errors, links, etc.
    compare_results
        The list returned from Conbench when hitting
        /compare/runs/{baseline_run_id}...{contender_run_id}, if a baseline run exists
        for this contender run. Contains a comparison for every case run to its
        baseline, including the statistics and regression analysis.
    benchmark_results
        The list returned from Conbench when hitting
        /benchmarks?run_id={contender_run_id}, if the contender run has errors. Contains
        info about each case in the contender run, including statistics and tracebacks.
        Only used when a baseline run doesn't exist, because otherwise all this
        information is already in the compare_results.
    """

    contender_info: dict
    baseline_info: Optional[dict] = None
    compare_results: Optional[List[dict]] = None
    benchmark_results: Optional[List[dict]] = None

    @property
    def baseline_is_parent(self) -> Optional[bool]:
        """Whether the baseline run is on a commit that's the immediate parent of the
        contender commit.
        """
        if self.baseline_info:
            return (
                self.baseline_info["commit"]["sha"]
                == self.contender_info["commit"]["parent_sha"]
            )

    @property
    def contender_reason(self) -> str:
        """The contender run reason."""
        return self.contender_info["reason"]

    @property
    def contender_datetime(self) -> str:
        """The contender run datetime."""
        dt: str = self.contender_info["timestamp"]
        return dt.replace("T", " ")

    @property
    def contender_link(self) -> str:
        """The link to the contender run page in the webapp."""
        return f"{self._app_url}/runs/{self.contender_id}"

    @property
    def compare_link(self) -> Optional[str]:
        """The link to the run comparison page in the webapp."""
        if self._compare_path:
            # self._compare_path has a leading slash already
            return f"{self._app_url}{self._compare_path}"

    def case_link(self, case_id: str) -> str:
        """Get the link to a specific benchmark case result in the webapp."""
        return f"{self._app_url}/benchmarks/{case_id}"

    @property
    def has_errors(self) -> bool:
        """Whether this run has any benchmark errors."""
        return self.contender_info["has_errors"]

    @property
    def contender_id(self) -> str:
        """The contender run_id."""
        return self.contender_info["id"]

    @property
    def _baseline_id(self) -> Optional[str]:
        """The baseline run_id."""
        if self.baseline_info:
            return self.baseline_info["id"]

    @property
    def _app_url(self) -> str:
        """The base URL to use for links to the webapp."""
        self_link: str = self.contender_info["links"]["self"]
        return self_link.rsplit("/api/", 1)[0]

    @property
    def _compare_path(self) -> Optional[str]:
        """The API path to get comparisons between the baseline and contender."""
        if self._baseline_id:
            return f"/compare/runs/{self._baseline_id}...{self.contender_id}/"

    @property
    def _baseline_path(self) -> Optional[str]:
        """The API path to get the baseline info."""
        baseline_link: Optional[str] = self.contender_info["links"].get("baseline")
        if baseline_link:
            return baseline_link.rsplit("/api", 1)[-1]


def get_comparison_to_baseline(
    conbench: ConbenchClient,
    contender_sha: str,
    z_score_threshold: Optional[float] = None,
) -> List[RunComparison]:
    """Get benchmark comparisons between the given contender commit and its baseline
    commit.

    The baseline commit is defined by conbench, and it's typically the most recent
    ancestor of the contender commit that's on the default branch.

    Parameters
    ----------
    conbench
        A ConbenchClient instance.
    contender_sha
        The commit SHA of the contender commit to compare. Needs to match EXACTLY what
        conbench has stored; typically 40 characters. It can't be a shortened version of
        the SHA.
    z_score_threshold
        The (positive) z-score threshold to send to the conbench compare endpoint.
        Benchmarks with a z-score more extreme than this threshold will be marked as
        regressions or improvements in the result. Default is to use whatever conbench
        uses for default.

    Returns
    -------
    List[RunComparison]
        Information about each run associated with the contender commit, and a
        comparison to its baseline run if that exists.
    """
    out_list = []
    contender_run_ids = [
        run["id"] for run in conbench.get("/runs/", params={"sha": contender_sha})
    ]
    if not contender_run_ids:
        fatal_and_log(
            f"Contender commit '{contender_sha}' doesn't have any runs in conbench."
        )

    log.info(f"Getting comparisons from {len(contender_run_ids)} run(s)")
    for run_id in contender_run_ids:
        run_comparison = RunComparison(contender_info=conbench.get(f"/runs/{run_id}/"))

        if run_comparison._baseline_path:
            run_comparison.baseline_info = conbench.get(run_comparison._baseline_path)

            compare_params = (
                {"threshold_z": z_score_threshold} if z_score_threshold else None
            )
            run_comparison.compare_results = conbench.get(
                run_comparison._compare_path, params=compare_params
            )

        else:
            log.warning(
                "Conbench could not find a baseline run for the contender run "
                f"{run_id}. A baseline run needs to be on the default branch in the "
                "same repository, with the same hardware and context, and have at "
                "least one of the same benchmark cases."
            )
            if run_comparison.has_errors:
                # get more information so we have more details about errors
                run_comparison.benchmark_results = conbench.get(
                    "/benchmarks/", params={"run_id": run_id}
                )

        out_list.append(run_comparison)

    return out_list
