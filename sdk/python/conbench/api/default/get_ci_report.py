from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.ci_report import CIReport
from ...models.error_model import ErrorModel
from ...models.get_ci_report_baseline import GetCiReportBaseline
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    repository: str | Unset = UNSET,
    commit_sha: str | Unset = UNSET,
    run_ids: str | Unset = UNSET,
    baseline_run_ids: str | Unset = UNSET,
    baseline: GetCiReportBaseline | Unset = UNSET,
    threshold: float | Unset = UNSET,
    threshold_z: float | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["repository"] = repository

    params["commit_sha"] = commit_sha

    params["run_ids"] = run_ids

    params["baseline_run_ids"] = baseline_run_ids

    json_baseline: str | Unset = UNSET
    if not isinstance(baseline, Unset):
        json_baseline = baseline.value

    params["baseline"] = json_baseline

    params["threshold"] = threshold

    params["threshold_z"] = threshold_z

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/ci/report",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CIReport | ErrorModel:
    if response.status_code == 200:
        response_200 = CIReport.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CIReport | ErrorModel]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    repository: str | Unset = UNSET,
    commit_sha: str | Unset = UNSET,
    run_ids: str | Unset = UNSET,
    baseline_run_ids: str | Unset = UNSET,
    baseline: GetCiReportBaseline | Unset = UNSET,
    threshold: float | Unset = UNSET,
    threshold_z: float | Unset = UNSET,
) -> Response[CIReport | ErrorModel]:
    """Get a PR/CI benchmark report

    Args:
        repository (str | Unset): Repository URL.
        commit_sha (str | Unset): Commit SHA.
        run_ids (str | Unset): Comma-separated contender run IDs.
        baseline_run_ids (str | Unset): Comma-separated explicit baseline run IDs, paired by
            position with run_ids.
        baseline (GetCiReportBaseline | Unset): Automatic baseline selector.
        threshold (float | Unset): Pairwise percent-change threshold. Defaults to 5.
        threshold_z (float | Unset): Lookback z-score threshold. Defaults to 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CIReport | ErrorModel]
    """

    kwargs = _get_kwargs(
        repository=repository,
        commit_sha=commit_sha,
        run_ids=run_ids,
        baseline_run_ids=baseline_run_ids,
        baseline=baseline,
        threshold=threshold,
        threshold_z=threshold_z,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    repository: str | Unset = UNSET,
    commit_sha: str | Unset = UNSET,
    run_ids: str | Unset = UNSET,
    baseline_run_ids: str | Unset = UNSET,
    baseline: GetCiReportBaseline | Unset = UNSET,
    threshold: float | Unset = UNSET,
    threshold_z: float | Unset = UNSET,
) -> CIReport | ErrorModel | None:
    """Get a PR/CI benchmark report

    Args:
        repository (str | Unset): Repository URL.
        commit_sha (str | Unset): Commit SHA.
        run_ids (str | Unset): Comma-separated contender run IDs.
        baseline_run_ids (str | Unset): Comma-separated explicit baseline run IDs, paired by
            position with run_ids.
        baseline (GetCiReportBaseline | Unset): Automatic baseline selector.
        threshold (float | Unset): Pairwise percent-change threshold. Defaults to 5.
        threshold_z (float | Unset): Lookback z-score threshold. Defaults to 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CIReport | ErrorModel
    """

    return sync_detailed(
        client=client,
        repository=repository,
        commit_sha=commit_sha,
        run_ids=run_ids,
        baseline_run_ids=baseline_run_ids,
        baseline=baseline,
        threshold=threshold,
        threshold_z=threshold_z,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    repository: str | Unset = UNSET,
    commit_sha: str | Unset = UNSET,
    run_ids: str | Unset = UNSET,
    baseline_run_ids: str | Unset = UNSET,
    baseline: GetCiReportBaseline | Unset = UNSET,
    threshold: float | Unset = UNSET,
    threshold_z: float | Unset = UNSET,
) -> Response[CIReport | ErrorModel]:
    """Get a PR/CI benchmark report

    Args:
        repository (str | Unset): Repository URL.
        commit_sha (str | Unset): Commit SHA.
        run_ids (str | Unset): Comma-separated contender run IDs.
        baseline_run_ids (str | Unset): Comma-separated explicit baseline run IDs, paired by
            position with run_ids.
        baseline (GetCiReportBaseline | Unset): Automatic baseline selector.
        threshold (float | Unset): Pairwise percent-change threshold. Defaults to 5.
        threshold_z (float | Unset): Lookback z-score threshold. Defaults to 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CIReport | ErrorModel]
    """

    kwargs = _get_kwargs(
        repository=repository,
        commit_sha=commit_sha,
        run_ids=run_ids,
        baseline_run_ids=baseline_run_ids,
        baseline=baseline,
        threshold=threshold,
        threshold_z=threshold_z,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    repository: str | Unset = UNSET,
    commit_sha: str | Unset = UNSET,
    run_ids: str | Unset = UNSET,
    baseline_run_ids: str | Unset = UNSET,
    baseline: GetCiReportBaseline | Unset = UNSET,
    threshold: float | Unset = UNSET,
    threshold_z: float | Unset = UNSET,
) -> CIReport | ErrorModel | None:
    """Get a PR/CI benchmark report

    Args:
        repository (str | Unset): Repository URL.
        commit_sha (str | Unset): Commit SHA.
        run_ids (str | Unset): Comma-separated contender run IDs.
        baseline_run_ids (str | Unset): Comma-separated explicit baseline run IDs, paired by
            position with run_ids.
        baseline (GetCiReportBaseline | Unset): Automatic baseline selector.
        threshold (float | Unset): Pairwise percent-change threshold. Defaults to 5.
        threshold_z (float | Unset): Lookback z-score threshold. Defaults to 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CIReport | ErrorModel
    """

    return (
        await asyncio_detailed(
            client=client,
            repository=repository,
            commit_sha=commit_sha,
            run_ids=run_ids,
            baseline_run_ids=baseline_run_ids,
            baseline=baseline,
            threshold=threshold,
            threshold_z=threshold_z,
        )
    ).parsed
