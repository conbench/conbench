from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...models.result_page import ResultPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    run_id: str | Unset = UNSET,
    batch_id: str | Unset = UNSET,
    run_reason: str | Unset = UNSET,
    earliest_timestamp: str | Unset = UNSET,
    latest_timestamp: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["run_id"] = run_id

    params["batch_id"] = batch_id

    params["run_reason"] = run_reason

    params["earliest_timestamp"] = earliest_timestamp

    params["latest_timestamp"] = latest_timestamp

    params["cursor"] = cursor

    params["page_size"] = page_size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/benchmark-results",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorModel | ResultPage:
    if response.status_code == 200:
        response_200 = ResultPage.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorModel | ResultPage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    run_id: str | Unset = UNSET,
    batch_id: str | Unset = UNSET,
    run_reason: str | Unset = UNSET,
    earliest_timestamp: str | Unset = UNSET,
    latest_timestamp: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> Response[ErrorModel | ResultPage]:
    """List and search benchmark results

    Args:
        run_id (str | Unset): Filter by run id.
        batch_id (str | Unset): Filter by batch id.
        run_reason (str | Unset): Filter by run reason.
        earliest_timestamp (str | Unset): Lower bound (inclusive), RFC3339.
        latest_timestamp (str | Unset): Upper bound (inclusive), RFC3339.
        cursor (str | Unset): Pagination cursor (previous page's last id).
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | ResultPage]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
        batch_id=batch_id,
        run_reason=run_reason,
        earliest_timestamp=earliest_timestamp,
        latest_timestamp=latest_timestamp,
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
    run_id: str | Unset = UNSET,
    batch_id: str | Unset = UNSET,
    run_reason: str | Unset = UNSET,
    earliest_timestamp: str | Unset = UNSET,
    latest_timestamp: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> ErrorModel | ResultPage | None:
    """List and search benchmark results

    Args:
        run_id (str | Unset): Filter by run id.
        batch_id (str | Unset): Filter by batch id.
        run_reason (str | Unset): Filter by run reason.
        earliest_timestamp (str | Unset): Lower bound (inclusive), RFC3339.
        latest_timestamp (str | Unset): Upper bound (inclusive), RFC3339.
        cursor (str | Unset): Pagination cursor (previous page's last id).
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | ResultPage
    """

    return sync_detailed(
        client=client,
        run_id=run_id,
        batch_id=batch_id,
        run_reason=run_reason,
        earliest_timestamp=earliest_timestamp,
        latest_timestamp=latest_timestamp,
        cursor=cursor,
        page_size=page_size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    run_id: str | Unset = UNSET,
    batch_id: str | Unset = UNSET,
    run_reason: str | Unset = UNSET,
    earliest_timestamp: str | Unset = UNSET,
    latest_timestamp: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> Response[ErrorModel | ResultPage]:
    """List and search benchmark results

    Args:
        run_id (str | Unset): Filter by run id.
        batch_id (str | Unset): Filter by batch id.
        run_reason (str | Unset): Filter by run reason.
        earliest_timestamp (str | Unset): Lower bound (inclusive), RFC3339.
        latest_timestamp (str | Unset): Upper bound (inclusive), RFC3339.
        cursor (str | Unset): Pagination cursor (previous page's last id).
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | ResultPage]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
        batch_id=batch_id,
        run_reason=run_reason,
        earliest_timestamp=earliest_timestamp,
        latest_timestamp=latest_timestamp,
        cursor=cursor,
        page_size=page_size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    run_id: str | Unset = UNSET,
    batch_id: str | Unset = UNSET,
    run_reason: str | Unset = UNSET,
    earliest_timestamp: str | Unset = UNSET,
    latest_timestamp: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    page_size: int | Unset = 100,
) -> ErrorModel | ResultPage | None:
    """List and search benchmark results

    Args:
        run_id (str | Unset): Filter by run id.
        batch_id (str | Unset): Filter by batch id.
        run_reason (str | Unset): Filter by run reason.
        earliest_timestamp (str | Unset): Lower bound (inclusive), RFC3339.
        latest_timestamp (str | Unset): Upper bound (inclusive), RFC3339.
        cursor (str | Unset): Pagination cursor (previous page's last id).
        page_size (int | Unset): Page size (max 1000). Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | ResultPage
    """

    return (
        await asyncio_detailed(
            client=client,
            run_id=run_id,
            batch_id=batch_id,
            run_reason=run_reason,
            earliest_timestamp=earliest_timestamp,
            latest_timestamp=latest_timestamp,
            cursor=cursor,
            page_size=page_size,
        )
    ).parsed
