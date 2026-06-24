from http import HTTPStatus
from typing import Any, cast

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    redirect_uri: str | Unset = UNSET,
    state: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> dict[str, Any]:

    cookies = {}
    if conbench_session is not UNSET:
        cookies["conbench_session"] = conbench_session

    params: dict[str, Any] = {}

    params["redirect_uri"] = redirect_uri

    params["state"] = state

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/auth/cli-start",
        "params": params,
        "cookies": cookies,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | ErrorModel:
    if response.status_code == 302:
        response_302 = cast(Any, None)
        return response_302

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | ErrorModel]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    redirect_uri: str | Unset = UNSET,
    state: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[Any | ErrorModel]:
    """Begin CLI loopback login

    Args:
        redirect_uri (str | Unset):
        state (str | Unset):
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorModel]
    """

    kwargs = _get_kwargs(
        redirect_uri=redirect_uri,
        state=state,
        conbench_session=conbench_session,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    redirect_uri: str | Unset = UNSET,
    state: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Any | ErrorModel | None:
    """Begin CLI loopback login

    Args:
        redirect_uri (str | Unset):
        state (str | Unset):
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorModel
    """

    return sync_detailed(
        client=client,
        redirect_uri=redirect_uri,
        state=state,
        conbench_session=conbench_session,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    redirect_uri: str | Unset = UNSET,
    state: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[Any | ErrorModel]:
    """Begin CLI loopback login

    Args:
        redirect_uri (str | Unset):
        state (str | Unset):
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorModel]
    """

    kwargs = _get_kwargs(
        redirect_uri=redirect_uri,
        state=state,
        conbench_session=conbench_session,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    redirect_uri: str | Unset = UNSET,
    state: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Any | ErrorModel | None:
    """Begin CLI loopback login

    Args:
        redirect_uri (str | Unset):
        state (str | Unset):
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorModel
    """

    return (
        await asyncio_detailed(
            client=client,
            redirect_uri=redirect_uri,
            state=state,
            conbench_session=conbench_session,
        )
    ).parsed
