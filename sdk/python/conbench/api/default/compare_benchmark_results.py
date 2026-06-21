from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.compare_result import CompareResult
from ...models.error_model import ErrorModel
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    baseline_result_id: str,
    contender_result_id: str,
    threshold: float | Unset = 5.0,
    threshold_z: float | Unset = 5.0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["baseline_result_id"] = baseline_result_id

    params["contender_result_id"] = contender_result_id

    params["threshold"] = threshold

    params["threshold_z"] = threshold_z

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/compare/benchmark-results",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CompareResult | ErrorModel:
    if response.status_code == 200:
        response_200 = CompareResult.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CompareResult | ErrorModel]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    baseline_result_id: str,
    contender_result_id: str,
    threshold: float | Unset = 5.0,
    threshold_z: float | Unset = 5.0,
) -> Response[CompareResult | ErrorModel]:
    """Compare two benchmark results

    Args:
        baseline_result_id (str): Baseline benchmark result id.
        contender_result_id (str): Contender benchmark result id.
        threshold (float | Unset): Pairwise percent-change threshold. Default: 5.0.
        threshold_z (float | Unset): Lookback z-score threshold. Default: 5.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CompareResult | ErrorModel]
    """

    kwargs = _get_kwargs(
        baseline_result_id=baseline_result_id,
        contender_result_id=contender_result_id,
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
    baseline_result_id: str,
    contender_result_id: str,
    threshold: float | Unset = 5.0,
    threshold_z: float | Unset = 5.0,
) -> CompareResult | ErrorModel | None:
    """Compare two benchmark results

    Args:
        baseline_result_id (str): Baseline benchmark result id.
        contender_result_id (str): Contender benchmark result id.
        threshold (float | Unset): Pairwise percent-change threshold. Default: 5.0.
        threshold_z (float | Unset): Lookback z-score threshold. Default: 5.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CompareResult | ErrorModel
    """

    return sync_detailed(
        client=client,
        baseline_result_id=baseline_result_id,
        contender_result_id=contender_result_id,
        threshold=threshold,
        threshold_z=threshold_z,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    baseline_result_id: str,
    contender_result_id: str,
    threshold: float | Unset = 5.0,
    threshold_z: float | Unset = 5.0,
) -> Response[CompareResult | ErrorModel]:
    """Compare two benchmark results

    Args:
        baseline_result_id (str): Baseline benchmark result id.
        contender_result_id (str): Contender benchmark result id.
        threshold (float | Unset): Pairwise percent-change threshold. Default: 5.0.
        threshold_z (float | Unset): Lookback z-score threshold. Default: 5.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CompareResult | ErrorModel]
    """

    kwargs = _get_kwargs(
        baseline_result_id=baseline_result_id,
        contender_result_id=contender_result_id,
        threshold=threshold,
        threshold_z=threshold_z,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    baseline_result_id: str,
    contender_result_id: str,
    threshold: float | Unset = 5.0,
    threshold_z: float | Unset = 5.0,
) -> CompareResult | ErrorModel | None:
    """Compare two benchmark results

    Args:
        baseline_result_id (str): Baseline benchmark result id.
        contender_result_id (str): Contender benchmark result id.
        threshold (float | Unset): Pairwise percent-change threshold. Default: 5.0.
        threshold_z (float | Unset): Lookback z-score threshold. Default: 5.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CompareResult | ErrorModel
    """

    return (
        await asyncio_detailed(
            client=client,
            baseline_result_id=baseline_result_id,
            contender_result_id=contender_result_id,
            threshold=threshold,
            threshold_z=threshold_z,
        )
    ).parsed
