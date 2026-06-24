from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...models.history_series import HistorySeries
from ...types import Response


def _get_kwargs(
    benchmark_result_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/history/{benchmark_result_id}".format(
            benchmark_result_id=quote(str(benchmark_result_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorModel | HistorySeries:
    if response.status_code == 200:
        response_200 = HistorySeries.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorModel | HistorySeries]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    benchmark_result_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorModel | HistorySeries]:
    """Get the history series for a benchmark result

    Args:
        benchmark_result_id (str): Benchmark result id whose history to load.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | HistorySeries]
    """

    kwargs = _get_kwargs(
        benchmark_result_id=benchmark_result_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    benchmark_result_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorModel | HistorySeries | None:
    """Get the history series for a benchmark result

    Args:
        benchmark_result_id (str): Benchmark result id whose history to load.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | HistorySeries
    """

    return sync_detailed(
        benchmark_result_id=benchmark_result_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    benchmark_result_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorModel | HistorySeries]:
    """Get the history series for a benchmark result

    Args:
        benchmark_result_id (str): Benchmark result id whose history to load.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | HistorySeries]
    """

    kwargs = _get_kwargs(
        benchmark_result_id=benchmark_result_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    benchmark_result_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorModel | HistorySeries | None:
    """Get the history series for a benchmark result

    Args:
        benchmark_result_id (str): Benchmark result id whose history to load.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | HistorySeries
    """

    return (
        await asyncio_detailed(
            benchmark_result_id=benchmark_result_id,
            client=client,
        )
    ).parsed
