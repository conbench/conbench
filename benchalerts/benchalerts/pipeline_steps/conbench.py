"""Pipeline steps to talk to Conbench."""

from enum import Enum
from typing import Any, Dict, List, Optional

from benchclients.conbench import LegacyConbenchClient
from benchclients.logging import fatal_and_log, log

from ..alert_pipeline import AlertPipelineStep
from ..conbench_dataclasses import FullComparisonInfo, RunComparisonInfo

ConbenchClient = LegacyConbenchClient


CONBENCH_ENV_VAR_HELP = """

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


class BaselineRunCandidates(Enum):
    """Types of baselines available from `/api/runs/{run_id}` in the
    `candidate_baseline_runs` field.
    """

    fork_point = "fork_point"
    head_of_default = "head_of_default"
    parent = "parent"


class GetConbenchZComparisonForRunsStep(AlertPipelineStep):
    (
        """An ``AlertPipeline`` step to get information from Conbench comparing run(s) to
    their baselines, using a z-score threshold. This is always the first step of the
    pipeline.

    Parameters
    ----------
    run_ids
        A list of Conbench run IDs of the runs to compare.
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
    """
        + CONBENCH_ENV_VAR_HELP
    )

    def __init__(
        self,
        run_ids: List[str],
        baseline_run_type: BaselineRunCandidates,
        z_score_threshold: Optional[float] = None,
        conbench_client: Optional[LegacyConbenchClient] = None,
        step_name: Optional[str] = None,
    ) -> None:
        super().__init__(step_name)
        self.run_ids = run_ids
        self.baseline_run_type = baseline_run_type
        self.z_score_threshold = z_score_threshold
        self.conbench_client = conbench_client or ConbenchClient()

    def run_step(self, previous_outputs: Dict[str, Any]) -> FullComparisonInfo:
        log.info(f"Getting comparisons from {len(self.run_ids)} run(s)")
        return FullComparisonInfo(
            run_comparisons=[
                self._get_one_run_comparison(run_id) for run_id in self.run_ids
            ]
        )

    def _get_one_run_comparison(self, run_id: str) -> RunComparisonInfo:
        """Create and populate one RunComparisonInfo instance."""
        run_comparison = RunComparisonInfo(
            contender_info=self.conbench_client.get(f"/runs/{run_id}/")
        )

        candidate_baseline_run = run_comparison.contender_info[
            "candidate_baseline_runs"
        ][self.baseline_run_type.value]
        baseline_run_id = candidate_baseline_run["baseline_run_id"]

        if baseline_run_id:
            run_comparison.baseline_info = self.conbench_client.get(
                f"/runs/{baseline_run_id}/"
            )

            # Get the comparison.
            compare_params = (
                {"threshold_z": self.z_score_threshold}
                if self.z_score_threshold
                else None
            )
            run_comparison.compare_results = self.conbench_client.get(
                run_comparison.compare_path, params=compare_params
            )

        else:
            log.warning(
                f"Conbench could not find a {self.baseline_run_type.value} baseline run "
                f"for the contender run {run_id}. Error: {candidate_baseline_run['error']}"
            )
            if run_comparison.has_errors:
                # get more information so we have more details about errors
                run_comparison.benchmark_results = self.conbench_client.get(
                    "/benchmarks/", params={"run_id": run_id}
                )

        return run_comparison


class GetConbenchZComparisonStep(GetConbenchZComparisonForRunsStep):
    (
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
    """
        + CONBENCH_ENV_VAR_HELP
    )

    def __init__(
        self,
        commit_hash: str,
        baseline_run_type: BaselineRunCandidates,
        z_score_threshold: Optional[float] = None,
        conbench_client: Optional[LegacyConbenchClient] = None,
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
        self.run_ids = [
            run["id"]
            for run in self.conbench_client.get(
                "/runs/", params={"sha": self.commit_hash}
            )
        ]
        if not self.run_ids:
            fatal_and_log(
                f"Contender commit '{self.commit_hash}' doesn't have any runs in Conbench."
            )

        return super().run_step(previous_outputs)
