"""Pipeline steps to talk to GitHub."""

from typing import Any, Dict, Optional, Tuple

from benchclients.logging import fatal_and_log, log

from ..alert_pipeline import AlertPipelineErrorHandler, AlertPipelineStep
from ..conbench_dataclasses import FullComparisonInfo
from ..integrations.github import CheckStatus, GitHubRepoClient
from ..message_formatting import Alerter


class GitHubCheckStep(AlertPipelineStep):
    """An ``AlertPipeline`` step to update a GitHub Check on a commit on GitHub, based
    on information collected in a previously-run ``GetConbenchZComparisonStep`` or
    ``GetConbenchZComparisonForRunsStep``.

    You must use GitHub App authentication to use this step.

    Parameters
    ----------
    commit_hash
        The commit hash to update.
    comparison_step_name
        The name of the ``GetConbenchZComparisonStep`` or
        ``GetConbenchZComparisonForRunsStep`` that ran earlier in the pipeline. If
        unspecified in that step, it defaults to the name of the step class, e.g.
        ``"GetConbenchZComparisonStep"``.
    repo
        The repo name to post the status to, in the form "owner/repo". Either provide
        this or ``github_client``.
    github_client
        A GitHubRepoClient instance. Either provide this or ``repo``.
    step_name
        The name for this step. If not given, will default to this class's name.
    external_id
        An optional reference to another system. This argument will set the
        "external_id" property of the posted GitHub Check, but do nothing else.
    build_url
        An optional build URL to include in the GitHub Check.
    alerter
        Advanced usage; should not be necessary in most cases. An optional Alerter
        instance to use to format the GitHub Check's status, title, summary, and
        details. If not provided, will default to ``Alerter()``.

    Returns
    -------
    dict
        The response body from the GitHub HTTP API as a dict.
    FullComparisonInfo
        The ``FullComparisonInfo`` object that the ``GetConbenchZComparisonStep`` or
        ``GetConbenchZComparisonForRunsStep`` output.

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
        comparison_step_name: str,
        repo: Optional[str] = None,
        github_client: Optional[GitHubRepoClient] = None,
        step_name: Optional[str] = None,
        external_id: Optional[str] = None,
        build_url: Optional[str] = None,
        alerter: Optional[Alerter] = None,
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
        self.external_id = external_id
        self.build_url = build_url
        self.alerter = alerter or Alerter()

    def run_step(
        self, previous_outputs: Dict[str, Any]
    ) -> Tuple[dict, FullComparisonInfo]:
        full_comparison: FullComparisonInfo = previous_outputs[
            self.comparison_step_name
        ]

        res = self.github_client.update_check(
            name="Conbench performance report",
            commit_hash=self.commit_hash,
            status=self.alerter.github_check_status(full_comparison),
            title=self.alerter.github_check_title(full_comparison),
            summary=self.alerter.github_check_summary(full_comparison, self.build_url),
            details=self.alerter.github_check_details(full_comparison),
            details_url=full_comparison.app_url,
            external_id=self.external_id,
        )
        log.debug(res)
        return res, full_comparison


class GitHubPRCommentAboutCheckStep(AlertPipelineStep):
    """An ``AlertPipeline`` step to make a comment on a PR about a GitHub Check that was
    created by a previously-run ``GitHubCheckStep``. This is useful if you're running
    benchmarks on a merge-commit, and no one is necessarily monitoring the Checks on the
    default branch. It should be set up to notify the PR that caused the merge-commit,
    so that the relevant people can take action if necessary.

    Parameters
    ----------
    pr_number
        The number of the PR to make the comment on.
    repo
        The repo name to make the comment on, in the form "owner/repo". Either provide
        this or ``github_client``.
    github_client
        A GitHubRepoClient instance. Either provide this or ``repo``.
    check_step_name
        The name of the ``GitHubCheckStep`` that ran earlier in the pipeline. Defaults
        to "GitHubCheckStep" (which was the default if no name was given to that step).
    step_name
        The name for this step. If not given, will default to this class's name.
    alerter
        Advanced usage; should not be necessary in most cases. An optional Alerter
        instance to use to format the comment. If not provided, will default to
        ``Alerter()``.

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
        pr_number: int,
        repo: Optional[str] = None,
        github_client: Optional[GitHubRepoClient] = None,
        check_step_name: str = "GitHubCheckStep",
        step_name: Optional[str] = None,
        alerter: Optional[Alerter] = None,
    ) -> None:
        super().__init__(step_name=step_name)
        self.pr_number = pr_number
        self.github_client = github_client or GitHubRepoClient(repo=repo or "")
        self.check_step_name = check_step_name
        self.alerter = alerter or Alerter()

    def run_step(self, previous_outputs: Dict[str, Any]) -> dict:
        check_details, full_comparison = previous_outputs[self.check_step_name]

        res = self.github_client.create_pull_request_comment(
            comment=self.alerter.github_pr_comment(
                full_comparison=full_comparison,
                check_link=check_details["html_url"],
            ),
            pull_number=self.pr_number,
        )
        return res


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
            summary=Alerter.clean(
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
