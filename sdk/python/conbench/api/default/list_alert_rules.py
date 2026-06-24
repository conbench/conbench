from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...models.list_alert_rules_output_body import ListAlertRulesOutputBody
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(authorization, Unset):
        headers["Authorization"] = authorization

    cookies = {}
    if conbench_session is not UNSET:
        cookies["conbench_session"] = conbench_session

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/alert-rules",
        "cookies": cookies,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorModel | ListAlertRulesOutputBody:
    if response.status_code == 200:
        response_200 = ListAlertRulesOutputBody.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorModel | ListAlertRulesOutputBody]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[ErrorModel | ListAlertRulesOutputBody]:
    """List the caller's alert rules

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | ListAlertRulesOutputBody]
    """

    kwargs = _get_kwargs(
        authorization=authorization,
        conbench_session=conbench_session,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> ErrorModel | ListAlertRulesOutputBody | None:
    """List the caller's alert rules

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | ListAlertRulesOutputBody
    """

    return sync_detailed(
        client=client,
        authorization=authorization,
        conbench_session=conbench_session,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[ErrorModel | ListAlertRulesOutputBody]:
    """List the caller's alert rules

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorModel | ListAlertRulesOutputBody]
    """

    kwargs = _get_kwargs(
        authorization=authorization,
        conbench_session=conbench_session,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> ErrorModel | ListAlertRulesOutputBody | None:
    """List the caller's alert rules

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorModel | ListAlertRulesOutputBody
    """

    return (
        await asyncio_detailed(
            client=client,
            authorization=authorization,
            conbench_session=conbench_session,
        )
    ).parsed
