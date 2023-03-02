"""Pipeline steps to talk to GitHub."""

from typing import Any, Dict, Optional

from benchclients.logging import fatal_and_log, log

from ..alert_pipeline import AlertPipelineErrorHandler, AlertPipelineStep
from ..conbench_dataclasses import FullComparisonInfo
from ..integrations.github import CheckStatus, GitHubRepoClient, StatusState
from ..message_formatting import _clean, github_check_details, github_check_summary


class GitHubCheckStep(AlertPipelineStep):
    """An ``AlertPipeline`` step to update a GitHub Check on a commit on GitHub, based
    on information collected in a previously-run ``GetConbenchZComparisonStep``.

    You must use GitHub App authentication to use this step.

    Parameters
    ----------
    repo
        The repo name to post the status to, in the form "owner/repo". Either provide
        this or ``github_client``.
    github_client
        A GitHubRepoClient instance. Either provide this or ``repo``.
    commit_hash
        The commit hash to update. Default is to use the same one that was analyzed in
        the GetConbenchZComparisonStep earlier in the pipeline.
    comparison_step_name
        The name of the ``GetConbenchZComparisonStep`` that ran earlier in the pipeline.
        Defaults to "GetConbenchZComparisonStep" (which was the default if no name was
        given to that step).
    warn_if_baseline_isnt_parent
        If True, will add a warning to any report generated where all baseline runs
        weren't on the contender commit's direct parent. This is informative to leave
        True (the default) for workflows run on the default branch, but might be noisy
        for workflows run on pull request commits.
    step_name
        The name for this step. If not given, will default to this class's name.

    Returns
    -------
    dict
        The response body from the GitHub HTTP API as a dict.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``GITHUB_APP_ID``
        The ID of a GitHub App that has been set up according to this package's
        instructions and installed to your repo. Only required if ``repo`` is provided
        instead of ``github_client``.
    ``GITHUB_APP_PRIVATE_KEY``
        The private key file contents of a GitHub App that has been set up according to
        this package's instructions and installed to your repo. Only required if
        ``repo`` is provided instead of ``github_client``.
    """

    def __init__(
        self,
        repo: Optional[str] = None,
        github_client: Optional[GitHubRepoClient] = None,
        commit_hash: Optional[str] = None,
        comparison_step_name: str = "GetConbenchZComparisonStep",
        warn_if_baseline_isnt_parent: bool = True,
        step_name: Optional[str] = None,
    ) -> None:
        super().__init__(step_name=step_name)
        self.github_client = github_client or GitHubRepoClient(repo=repo or "")
        if not self.github_client._is_github_app_token:
            fatal_and_log(
                "Your GitHubRepoClient must be authenticated as a GitHub App "
                "to use the GitHubCheckStep"
            )
        self.commit_hash = commit_hash
        self.comparison_step_name = comparison_step_name
        self.warn_if_baseline_isnt_parent = warn_if_baseline_isnt_parent

    def run_step(self, previous_outputs: Dict[str, Any]) -> dict:
        full_comparison: FullComparisonInfo = previous_outputs[
            self.comparison_step_name
        ]

        res = self.github_client.update_check(
            name="Conbench performance report",
            commit_hash=self.commit_hash or full_comparison.commit_hash,
            status=self._default_check_status(full_comparison),
            title=(
                "Some benchmarks had errors"
                if full_comparison.benchmarks_with_errors
                else f"Found {len(full_comparison.benchmarks_with_z_regressions)} regression(s)"
            ),
            summary=self._default_check_summary(
                full_comparison,
                self.warn_if_baseline_isnt_parent,
            ),
            details=self._default_check_details(full_comparison),
            # point to the homepage table filtered to runs of this commit
            details_url=f"{full_comparison.app_url}/?search={full_comparison.commit_hash}",
        )
        log.debug(res)
        return res

    # TODO: a way to override the following behavior
    # (see https://github.com/conbench/conbench/issues/774)

    @staticmethod
    def _default_check_status(full_comparison: FullComparisonInfo) -> CheckStatus:
        """Return a different status based on errors and regressions."""
        if full_comparison.benchmarks_with_errors:
            return CheckStatus.ACTION_REQUIRED
        elif full_comparison.no_baseline_runs:
            return CheckStatus.SKIPPED
        elif full_comparison.benchmarks_with_z_regressions:
            return CheckStatus.FAILURE
        else:
            return CheckStatus.SUCCESS

    @staticmethod
    def _default_check_summary(
        full_comparison: FullComparisonInfo, warn_if_baseline_isnt_parent: bool
    ) -> str:
        return github_check_summary(full_comparison, warn_if_baseline_isnt_parent)

    @staticmethod
    def _default_check_details(full_comparison: FullComparisonInfo) -> Optional[str]:
        return github_check_details(full_comparison)


class GitHubStatusStep(AlertPipelineStep):
    """An ``AlertPipeline`` step to update a GitHub Status on a commit on GitHub, based
    on information collected in a previously-run ``GetConbenchZComparisonStep``.

    Parameters
    ----------
    repo
        The repo name to post the status to, in the form "owner/repo". Either provide
        this or ``github_client``.
    github_client
        A GitHubRepoClient instance. Either provide this or ``repo``.
    commit_hash
        The commit hash to update. Default is to use the same one that was analyzed in
        the GetConbenchZComparisonStep earlier in the pipeline.
    comparison_step_name
        The name of the ``GetConbenchZComparisonStep`` that ran earlier in the pipeline.
        Defaults to "GetConbenchZComparisonStep" (which was the default if no name was
        given to that step).
    step_name
        The name for this step. If not given, will default to this class's name.

    Returns
    -------
    dict
        The response body from the GitHub HTTP API as a dict.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``GITHUB_APP_ID``
        The ID of a GitHub App that has been set up according to this package's
        instructions and installed to your repo. Recommended over ``GITHUB_API_TOKEN``.
        Only required if ``repo`` is provided instead of ``github_client``.
    ``GITHUB_APP_PRIVATE_KEY``
        The private key file contents of a GitHub App that has been set up according to
        this package's instructions and installed to your repo. Recommended over
        ``GITHUB_API_TOKEN``. Only required if ``repo`` is provided instead of
        ``github_client``.
    ``GITHUB_API_TOKEN``
        A GitHub Personal Access Token with the ``repo:status`` permission. Only
        required if not authenticating with a GitHub App, and if ``repo`` is provided
        instead of ``github_client``.
    """

    def __init__(
        self,
        repo: Optional[str] = None,
        github_client: Optional[GitHubRepoClient] = None,
        commit_hash: Optional[str] = None,
        comparison_step_name: str = "GetConbenchZComparisonStep",
        step_name: Optional[str] = None,
    ) -> None:
        super().__init__(step_name=step_name)
        self.github_client = github_client or GitHubRepoClient(repo=repo or "")
        self.commit_hash = commit_hash
        self.comparison_step_name = comparison_step_name

    def run_step(self, previous_outputs: Dict[str, Any]) -> dict:
        full_comparison: FullComparisonInfo = previous_outputs[
            self.comparison_step_name
        ]

        res = self.github_client.update_commit_status(
            commit_hash=self.commit_hash or full_comparison.commit_hash,
            title="conbench",
            description=self._default_status_description(full_comparison),
            state=self._default_status_state(full_comparison),
            # point to the homepage table filtered to runs of this commit
            details_url=f"{full_comparison.app_url}/?search={full_comparison.commit_hash}",
        )
        log.debug(res)
        return res

    # TODO: a way to override the following behavior
    # (see https://github.com/conbench/conbench/issues/774)

    @staticmethod
    def _default_status_state(full_comparison: FullComparisonInfo) -> StatusState:
        """Return a different status based on errors and regressions."""
        if full_comparison.benchmarks_with_errors:
            return StatusState.FAILURE
        elif full_comparison.no_baseline_runs:
            return StatusState.SUCCESS
        elif full_comparison.benchmarks_with_z_regressions:
            return StatusState.FAILURE
        else:
            return StatusState.SUCCESS

    @staticmethod
    def _default_status_description(full_comparison: FullComparisonInfo) -> str:
        if full_comparison.benchmarks_with_errors:
            return "Some benchmarks had errors"
        elif full_comparison.no_baseline_runs:
            return "Could not find any baseline runs to compare to"
        else:
            return (
                f"There were {len(full_comparison.benchmarks_with_z_regressions)} "
                "benchmark regression(s) in this commit"
            )


class GitHubCheckErrorHandler(AlertPipelineErrorHandler):
    """Handle errors in a pipeline by updating a GitHub Check status.

    Parameters
    ----------
    commit_hash
        The commit hash to update.
    repo
        The repo name to post the status to, in the form "owner/repo". Either provide
        this or ``github_client``.
    github_client
        A GitHubRepoClient instance. Either provide this or ``repo``.
    build_url
        An optional build URL to include in the GitHub Check.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``GITHUB_APP_ID``
        The ID of a GitHub App that has been set up according to this package's
        instructions and installed to your repo. Only required if ``repo`` is provided
        instead of ``github_client``.
    ``GITHUB_APP_PRIVATE_KEY``
        The private key file contents of a GitHub App that has been set up according to
        this package's instructions and installed to your repo. Only required if
        ``repo`` is provided instead of ``github_client``.
    """

    def __init__(
        self,
        commit_hash: str,
        repo: Optional[str] = None,
        github_client: Optional[GitHubRepoClient] = None,
        build_url: Optional[str] = None,
    ) -> None:
        self.commit_hash = commit_hash
        self.github_client = github_client or GitHubRepoClient(repo=repo or "")
        if not self.github_client._is_github_app_token:
            fatal_and_log(
                "Your GitHubRepoClient must be authenticated as a GitHub App "
                "to use the GitHubCheckErrorHandler"
            )
        self.build_url = build_url

    def handle_error(self, exc: BaseException, traceback: str) -> None:
        res = self.github_client.update_check(
            name="Conbench performance report",
            commit_hash=self.commit_hash,
            summary=_clean(
                """
                The CI build running the regression analysis failed. This does not
                necessarily mean this commit has benchmark regressions, but there is an
                error that must be resolved before we can find out.
                """
            ),
            details=f"Error: `{repr(exc)}`\n\nSee build link below.",
            status=CheckStatus.NEUTRAL,
            title="Error when analyzing performance",
            details_url=self.build_url,
        )
        log.debug(res)


class GitHubStatusErrorHandler(AlertPipelineErrorHandler):
    """Handle errors in a pipeline by updating a GitHub Status.

    Parameters
    ----------
    commit_hash
        The commit hash to update.
    repo
        The repo name to post the status to, in the form "owner/repo". Either provide
        this or ``github_client``.
    github_client
        A GitHubRepoClient instance. Either provide this or ``repo``.
    build_url
        An optional build URL to include in the GitHub Check.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``GITHUB_APP_ID``
        The ID of a GitHub App that has been set up according to this package's
        instructions and installed to your repo. Recommended over ``GITHUB_API_TOKEN``.
        Only required if ``repo`` is provided instead of ``github_client``.
    ``GITHUB_APP_PRIVATE_KEY``
        The private key file contents of a GitHub App that has been set up according to
        this package's instructions and installed to your repo. Recommended over
        ``GITHUB_API_TOKEN``. Only required if ``repo`` is provided instead of
        ``github_client``.
    ``GITHUB_API_TOKEN``
        A GitHub Personal Access Token with the ``repo:status`` permission. Only
        required if not authenticating with a GitHub App, and if ``repo`` is provided
        instead of ``github_client``.
    """

    def __init__(
        self,
        commit_hash: str,
        repo: Optional[str] = None,
        github_client: Optional[GitHubRepoClient] = None,
        build_url: Optional[str] = None,
    ) -> None:
        self.commit_hash = commit_hash
        self.github_client = github_client or GitHubRepoClient(repo=repo or "")
        self.build_url = build_url

    def handle_error(self, exc: BaseException, traceback: str) -> None:
        res = self.github_client.update_commit_status(
            commit_hash=self.commit_hash,
            title="conbench",
            description=f"Failed finding regressions: {exc}",
            state=StatusState.ERROR,
            details_url=self.build_url,
        )
        log.debug(res)
