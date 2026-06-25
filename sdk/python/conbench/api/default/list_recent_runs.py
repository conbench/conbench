from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...models.recent_runs_page import RecentRunsPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    page_size: int | Unset = 25,
    include_attention: bool | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["page_size"] = page_size

    params["include_attention"] = include_attention

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/runs/recent",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorModel | RecentRunsPage:
    if response.status_code == 200:
        response_200 = RecentRunsPage.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorModel | RecentRunsPage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    page_size: int | Unset = 25,
    include_attention: bool | Unset = UNSET,
) -> Response[ErrorModel | RecentRunsPage]:
    """List recent benchmark runs

    Args:
        page_size (int | Unset): Page size (max 100). Default: 25.
        include_attention (bool | Unset): Include bounded CI attention summaries for the newest
            runs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | RecentRunsPage]
    """

    kwargs = _get_kwargs(
        page_size=page_size,
        include_attention=include_attention,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    page_size: int | Unset = 25,
    include_attention: bool | Unset = UNSET,
) -> ErrorModel | RecentRunsPage | None:
    """List recent benchmark runs

    Args:
        page_size (int | Unset): Page size (max 100). Default: 25.
        include_attention (bool | Unset): Include bounded CI attention summaries for the newest
            runs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | RecentRunsPage
    """

    return sync_detailed(
        client=client,
        page_size=page_size,
        include_attention=include_attention,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    page_size: int | Unset = 25,
    include_attention: bool | Unset = UNSET,
) -> Response[ErrorModel | RecentRunsPage]:
    """List recent benchmark runs

    Args:
        page_size (int | Unset): Page size (max 100). Default: 25.
        include_attention (bool | Unset): Include bounded CI attention summaries for the newest
            runs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | RecentRunsPage]
    """

    kwargs = _get_kwargs(
        page_size=page_size,
        include_attention=include_attention,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    page_size: int | Unset = 25,
    include_attention: bool | Unset = UNSET,
) -> ErrorModel | RecentRunsPage | None:
    """List recent benchmark runs

    Args:
        page_size (int | Unset): Page size (max 100). Default: 25.
        include_attention (bool | Unset): Include bounded CI attention summaries for the newest
            runs.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | RecentRunsPage
    """

    return (
        await asyncio_detailed(
            client=client,
            page_size=page_size,
            include_attention=include_attention,
        )
    ).parsed
