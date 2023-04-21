"""Pipeline steps to talk to Conbench."""

from typing import Any, Dict, Optional

from benchclients.conbench import LegacyConbenchClient
from benchclients.logging import fatal_and_log, log

from ..alert_pipeline import AlertPipelineStep
from ..conbench_dataclasses import FullComparisonInfo, RunComparisonInfo

ConbenchClient = LegacyConbenchClient


class GetConbenchZComparisonStep(AlertPipelineStep):
    """An ``AlertPipeline`` step to get information from Conbench comparing the runs on
    a contender commit to their baselines, using a z-score threshold. This is always the
    first step of the pipeline.

    Parameters
    ----------
    commit_hash
        The commit hash of the contender commit to compare. Needs to match EXACTLY what
        Conbench has stored; typically 40 characters. It can't be a shortened version of
        the hash.
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
        z_score_threshold: Optional[float] = None,
        conbench_client: Optional[ConbenchClient] = None,
        step_name: Optional[str] = None,
    ) -> None:
        super().__init__(step_name)
        self.commit_hash = commit_hash
        self.z_score_threshold = z_score_threshold
        self.conbench_client = conbench_client or ConbenchClient()

    def run_step(self, previous_outputs: Dict[str, Any]) -> FullComparisonInfo:
        contender_run_ids = [
            run["id"]
            for run in self.conbench_client.get(
                "/runs/", params={"sha": self.commit_hash}
            )
        ]
        if not contender_run_ids:
            fatal_and_log(
                f"Contender commit '{self.commit_hash}' doesn't have any runs in Conbench."
            )

        log.info(f"Getting comparisons from {len(contender_run_ids)} run(s)")
        return FullComparisonInfo(
            run_comparisons=[
                self._get_one_run_comparison(run_id) for run_id in contender_run_ids
            ]
        )

    def _get_one_run_comparison(self, run_id: str) -> RunComparisonInfo:
        """Create and populate one RunComparisonInfo instance."""
        run_comparison = RunComparisonInfo(
            contender_info=self.conbench_client.get(f"/runs/{run_id}/")
        )

        if run_comparison.baseline_path:
            # A baseline run exists. Get it.
            run_comparison.baseline_info = self.conbench_client.get(
                run_comparison.baseline_path
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
                "Conbench could not find a baseline run for the contender run "
                f"{run_id}. A baseline run needs to be on the default branch in the "
                "same repository, with the same hardware, and have at least one of the "
                "same benchmark case/context pairs."
            )
            if run_comparison.has_errors:
                # get more information so we have more details about errors
                run_comparison.benchmark_results = self.conbench_client.get(
                    "/benchmarks/", params={"run_id": run_id}
                )

        return run_comparison
