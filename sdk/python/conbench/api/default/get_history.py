from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...models.history_series import HistorySeries
from ...types import UNSET, Response


def _get_kwargs(
    *,
    fingerprint: str,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["fingerprint"] = fingerprint

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/history",
        "params": params,
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
    *,
    client: AuthenticatedClient | Client,
    fingerprint: str,
) -> Response[ErrorModel | HistorySeries]:
    """Get a history series by fingerprint

    Args:
        fingerprint (str): History fingerprint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | HistorySeries]
    """

    kwargs = _get_kwargs(
        fingerprint=fingerprint,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    fingerprint: str,
) -> ErrorModel | HistorySeries | None:
    """Get a history series by fingerprint

    Args:
        fingerprint (str): History fingerprint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | HistorySeries
    """

    return sync_detailed(
        client=client,
        fingerprint=fingerprint,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    fingerprint: str,
) -> Response[ErrorModel | HistorySeries]:
    """Get a history series by fingerprint

    Args:
        fingerprint (str): History fingerprint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | HistorySeries]
    """

    kwargs = _get_kwargs(
        fingerprint=fingerprint,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    fingerprint: str,
) -> ErrorModel | HistorySeries | None:
    """Get a history series by fingerprint

    Args:
        fingerprint (str): History fingerprint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | HistorySeries
    """

    return (
        await asyncio_detailed(
            client=client,
            fingerprint=fingerprint,
        )
    ).parsed
