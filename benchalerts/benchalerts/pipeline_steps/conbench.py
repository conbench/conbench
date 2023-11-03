"""Pipeline steps to talk to Conbench."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from benchclients.conbench import ConbenchClient
from benchclients.http import RetryingHTTPClientNonRetryableResponse
from benchclients.logging import log

from ..alert_pipeline import AlertPipelineStep
from ..conbench_dataclasses import FullComparisonInfo, RunComparisonInfo


class BaselineRunCandidates(Enum):
    """Types of baselines available from `/api/runs/{run_id}` in the
    `candidate_baseline_runs` field.
    """

    fork_point = "fork_point"
    latest_default = "latest_default"
    parent = "parent"


class GetConbenchZComparisonForRunsStep(AlertPipelineStep):
    """An ``AlertPipeline`` step to get information from Conbench comparing run(s) to
    their baselines, using a z-score threshold. This is always the first step of the
    pipeline.

    Parameters
    ----------
    run_ids
        A list of Conbench run IDs of the runs to compare. There must be at least one,
        and they must all be from the same commit.
    baseline_run_type
        The type of baseline to use. See ``BaselineRunCandidates`` for options.
    z_score_threshold
        The (positive) z-score threshold to send to the Conbench compare endpoint.
        Benchmarks with a z-score more extreme than this threshold will be marked as
        regressions or improvements in the result. Default is to use whatever Conbench
        uses for default (at the time of writing, this is 5).
    conbench_client
        A ConbenchClient instance. If not given, one will be created using the standard
        environment variables.
    step_name
        The name for this step. If not given, will default to this class's name.

    Returns
    -------
    FullComparisonInfo
        Information about each run associated with the contender commit, and a
        comparison to its baseline run if that exists.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``CONBENCH_URL``
        The URL of the Conbench server. Only required if ``conbench_client`` is not
        provided.
    ``CONBENCH_EMAIL``
        The email to use for Conbench login. Only required if ``conbench_client`` is not
        provided and the server is private.
    ``CONBENCH_PASSWORD``
        The password to use for Conbench login. Only required if ``conbench_client`` is
        not provided and the server is private.
    """

    def __init__(
        self,
        run_ids: List[str],
        baseline_run_type: BaselineRunCandidates,
        z_score_threshold: Optional[float] = None,
        conbench_client: Optional[ConbenchClient] = None,
        step_name: Optional[str] = None,
    ) -> None:
        super().__init__(step_name)
        self.run_ids = run_ids
        self.baseline_run_type = baseline_run_type
        self.z_score_threshold = z_score_threshold
        self.conbench_client = conbench_client or ConbenchClient()

    def run_step(self, previous_outputs: Dict[str, Any]) -> FullComparisonInfo:
        log.info(f"Getting comparisons from {len(self.run_ids)} run(s)")
        run_comparisons: List[RunComparisonInfo] = []
        for run_id in self.run_ids:
            run_comparison = self._get_one_run_comparison(run_id)
            if run_comparison:
                run_comparisons.append(run_comparison)

        return FullComparisonInfo(run_comparisons=run_comparisons)

    def _get_one_run_comparison(self, run_id: str) -> Optional[RunComparisonInfo]:
        """Create and populate one RunComparisonInfo instance. Return None if the run
        is not found on the Conbench server.
        """
        try:
            contender_info = self.conbench_client.get(f"/runs/{run_id}/")
        except RetryingHTTPClientNonRetryableResponse as e:
            if e.error_response.status_code == 404:
                log.info(
                    f"Conbench couldn't find run {run_id}; not including it for analysis"
                )
                return None
            raise

        run_comparison = RunComparisonInfo(
            conbench_api_url=self.conbench_client._base_url,
            contender_info=contender_info,
            baseline_run_type=self.baseline_run_type.value,
        )

        if run_comparison.baseline_id:
            # Get the comparison.
            compare_params: Dict[str, Union[int, float]] = {"page_size": 500}
            if self.z_score_threshold:
                compare_params["threshold_z"] = self.z_score_threshold
            run_comparison.compare_results = self.conbench_client.get_all(
                run_comparison.compare_path, params=compare_params
            )

        else:
            log.warning(
                f"Conbench could not find a {self.baseline_run_type.value} baseline run "
                f"for the contender run {run_id}. Error: {run_comparison.baseline_error}"
            )
            # Just get information about the contender benchmark results.
            run_comparison.benchmark_results = self.conbench_client.get_all(
                "/benchmark-results/", params={"run_id": run_id, "page_size": 1000}
            )

        return run_comparison


class GetConbenchZComparisonStep(GetConbenchZComparisonForRunsStep):
    """An ``AlertPipeline`` step to get information from Conbench comparing the runs on
    a contender commit to their baselines, using a z-score threshold. This is always the
    first step of the pipeline.

    Parameters
    ----------
    commit_hash
        The commit hash of the contender commit to compare. Needs to match EXACTLY what
        Conbench has stored; typically 40 characters. It can't be a shortened version of
        the hash.
    baseline_run_type
        The type of baseline to use. See ``BaselineCandidates`` for options.
    z_score_threshold
        The (positive) z-score threshold to send to the Conbench compare endpoint.
        Benchmarks with a z-score more extreme than this threshold will be marked as
        regressions or improvements in the result. Default is to use whatever Conbench
        uses for default (at the time of writing, this is 5).
    conbench_client
        A ConbenchClient instance. If not given, one will be created using the standard
        environment variables.
    step_name
        The name for this step. If not given, will default to this class's name.

    Returns
    -------
    FullComparisonInfo
        Information about each run associated with the contender commit, and a
        comparison to its baseline run if that exists.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``CONBENCH_URL``
        The URL of the Conbench server. Only required if ``conbench_client`` is not
        provided.
    ``CONBENCH_EMAIL``
        The email to use for Conbench login. Only required if ``conbench_client`` is not
        provided and the server is private.
    ``CONBENCH_PASSWORD``
        The password to use for Conbench login. Only required if ``conbench_client`` is
        not provided and the server is private.
    """

    def __init__(
        self,
        commit_hash: str,
        baseline_run_type: BaselineRunCandidates,
        z_score_threshold: Optional[float] = None,
        conbench_client: Optional[ConbenchClient] = None,
        step_name: Optional[str] = None,
    ) -> None:
        super().__init__(
            run_ids=[],
            baseline_run_type=baseline_run_type,
            z_score_threshold=z_score_threshold,
            conbench_client=conbench_client,
            step_name=step_name,
        )
        self.commit_hash = commit_hash

    def run_step(self, previous_outputs: Dict[str, Any]) -> FullComparisonInfo:
        runs = self.conbench_client.get_all(
            "/runs/", params={"commit_hash": self.commit_hash, "page_size": 1000}
        )
        self.run_ids = [run["id"] for run in runs]
        return super().run_step(previous_outputs)
