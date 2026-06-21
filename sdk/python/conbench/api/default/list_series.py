from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...models.series_page import SeriesPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: str | Unset = UNSET,
    hardware: str | Unset = UNSET,
    repository: str | Unset = UNSET,
    fingerprint: str | Unset = UNSET,
    active_since: str | Unset = UNSET,
    active_until: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    params["hardware"] = hardware

    params["repository"] = repository

    params["fingerprint"] = fingerprint

    params["active_since"] = active_since

    params["active_until"] = active_until

    params["cursor"] = cursor

    params["page_size"] = page_size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/series",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorModel | SeriesPage:
    if response.status_code == 200:
        response_200 = SeriesPage.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorModel | SeriesPage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = UNSET,
    hardware: str | Unset = UNSET,
    repository: str | Unset = UNSET,
    fingerprint: str | Unset = UNSET,
    active_since: str | Unset = UNSET,
    active_until: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> Response[ErrorModel | SeriesPage]:
    """List and search benchmark series

    Args:
        q (str | Unset): Substring match on case name and case tags.
        hardware (str | Unset): Filter by hardware name.
        repository (str | Unset): Filter by repository URL.
        fingerprint (str | Unset): Filter by history fingerprint.
        active_since (str | Unset): Latest commit at or after this instant, RFC3339.
        active_until (str | Unset): Latest commit at or before this instant, RFC3339.
        cursor (str | Unset): Pagination cursor from a previous page's next_page_cursor.
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | SeriesPage]
    """

    kwargs = _get_kwargs(
        q=q,
        hardware=hardware,
        repository=repository,
        fingerprint=fingerprint,
        active_since=active_since,
        active_until=active_until,
        cursor=cursor,
        page_size=page_size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = UNSET,
    hardware: str | Unset = UNSET,
    repository: str | Unset = UNSET,
    fingerprint: str | Unset = UNSET,
    active_since: str | Unset = UNSET,
    active_until: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> ErrorModel | SeriesPage | None:
    """List and search benchmark series

    Args:
        q (str | Unset): Substring match on case name and case tags.
        hardware (str | Unset): Filter by hardware name.
        repository (str | Unset): Filter by repository URL.
        fingerprint (str | Unset): Filter by history fingerprint.
        active_since (str | Unset): Latest commit at or after this instant, RFC3339.
        active_until (str | Unset): Latest commit at or before this instant, RFC3339.
        cursor (str | Unset): Pagination cursor from a previous page's next_page_cursor.
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | SeriesPage
    """

    return sync_detailed(
        client=client,
        q=q,
        hardware=hardware,
        repository=repository,
        fingerprint=fingerprint,
        active_since=active_since,
        active_until=active_until,
        cursor=cursor,
        page_size=page_size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = UNSET,
    hardware: str | Unset = UNSET,
    repository: str | Unset = UNSET,
    fingerprint: str | Unset = UNSET,
    active_since: str | Unset = UNSET,
    active_until: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> Response[ErrorModel | SeriesPage]:
    """List and search benchmark series

    Args:
        q (str | Unset): Substring match on case name and case tags.
        hardware (str | Unset): Filter by hardware name.
        repository (str | Unset): Filter by repository URL.
        fingerprint (str | Unset): Filter by history fingerprint.
        active_since (str | Unset): Latest commit at or after this instant, RFC3339.
        active_until (str | Unset): Latest commit at or before this instant, RFC3339.
        cursor (str | Unset): Pagination cursor from a previous page's next_page_cursor.
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | SeriesPage]
    """

    kwargs = _get_kwargs(
        q=q,
        hardware=hardware,
        repository=repository,
        fingerprint=fingerprint,
        active_since=active_since,
        active_until=active_until,
        cursor=cursor,
        page_size=page_size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = UNSET,
    hardware: str | Unset = UNSET,
    repository: str | Unset = UNSET,
    fingerprint: str | Unset = UNSET,
    active_since: str | Unset = UNSET,
    active_until: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> ErrorModel | SeriesPage | None:
    """List and search benchmark series

    Args:
        q (str | Unset): Substring match on case name and case tags.
        hardware (str | Unset): Filter by hardware name.
        repository (str | Unset): Filter by repository URL.
        fingerprint (str | Unset): Filter by history fingerprint.
        active_since (str | Unset): Latest commit at or after this instant, RFC3339.
        active_until (str | Unset): Latest commit at or before this instant, RFC3339.
        cursor (str | Unset): Pagination cursor from a previous page's next_page_cursor.
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | SeriesPage
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            hardware=hardware,
            repository=repository,
            fingerprint=fingerprint,
            active_since=active_since,
            active_until=active_until,
            cursor=cursor,
            page_size=page_size,
        )
    ).parsed
