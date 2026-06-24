from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...models.list_alert_events_output_body import ListAlertEventsOutputBody
from ...types import UNSET, Response, Unset


def _get_kwargs(
    id: str,
    *,
    limit: int | Unset = 50,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(authorization, Unset):
        headers["Authorization"] = authorization

    cookies = {}
    if conbench_session is not UNSET:
        cookies["conbench_session"] = conbench_session

    params: dict[str, Any] = {}

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/alert-rules/{id}/events".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
        "cookies": cookies,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorModel | ListAlertEventsOutputBody:
    if response.status_code == 200:
        response_200 = ListAlertEventsOutputBody.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorModel | ListAlertEventsOutputBody]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = 50,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[ErrorModel | ListAlertEventsOutputBody]:
    """List alert events for one rule

    Args:
        id (str):
        limit (int | Unset): Maximum events to return. Default: 50.
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | ListAlertEventsOutputBody]
    """

    kwargs = _get_kwargs(
        id=id,
        limit=limit,
        authorization=authorization,
        conbench_session=conbench_session,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = 50,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> ErrorModel | ListAlertEventsOutputBody | None:
    """List alert events for one rule

    Args:
        id (str):
        limit (int | Unset): Maximum events to return. Default: 50.
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | ListAlertEventsOutputBody
    """

    return sync_detailed(
        id=id,
        client=client,
        limit=limit,
        authorization=authorization,
        conbench_session=conbench_session,
    ).parsed


async def asyncio_detailed(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = 50,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[ErrorModel | ListAlertEventsOutputBody]:
    """List alert events for one rule

    Args:
        id (str):
        limit (int | Unset): Maximum events to return. Default: 50.
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | ListAlertEventsOutputBody]
    """

    kwargs = _get_kwargs(
        id=id,
        limit=limit,
        authorization=authorization,
        conbench_session=conbench_session,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: str,
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = 50,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> ErrorModel | ListAlertEventsOutputBody | None:
    """List alert events for one rule

    Args:
        id (str):
        limit (int | Unset): Maximum events to return. Default: 50.
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | ListAlertEventsOutputBody
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            limit=limit,
            authorization=authorization,
            conbench_session=conbench_session,
        )
    ).parsed
