from http import HTTPStatus
from typing import Any, cast

import httpx

from ...client import AuthenticatedClient, Client
from ...models.error_model import ErrorModel
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    state: str | Unset = UNSET,
    code: str | Unset = UNSET,
    conbench_pending: str | Unset = UNSET,
) -> dict[str, Any]:

    cookies = {}
    if conbench_pending is not UNSET:
        cookies["conbench_pending"] = conbench_pending

    params: dict[str, Any] = {}

    params["state"] = state

    params["code"] = code

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/auth/callback",
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
    state: str | Unset = UNSET,
    code: str | Unset = UNSET,
    conbench_pending: str | Unset = UNSET,
) -> Response[Any | ErrorModel]:
    """OIDC callback

    Args:
        state (str | Unset):
        code (str | Unset):
        conbench_pending (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorModel]
    """

    kwargs = _get_kwargs(
        state=state,
        code=code,
        conbench_pending=conbench_pending,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    state: str | Unset = UNSET,
    code: str | Unset = UNSET,
    conbench_pending: str | Unset = UNSET,
) -> Any | ErrorModel | None:
    """OIDC callback

    Args:
        state (str | Unset):
        code (str | Unset):
        conbench_pending (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorModel
    """

    return sync_detailed(
        client=client,
        state=state,
        code=code,
        conbench_pending=conbench_pending,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    state: str | Unset = UNSET,
    code: str | Unset = UNSET,
    conbench_pending: str | Unset = UNSET,
) -> Response[Any | ErrorModel]:
    """OIDC callback

    Args:
        state (str | Unset):
        code (str | Unset):
        conbench_pending (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorModel]
    """

    kwargs = _get_kwargs(
        state=state,
        code=code,
        conbench_pending=conbench_pending,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    state: str | Unset = UNSET,
    code: str | Unset = UNSET,
    conbench_pending: str | Unset = UNSET,
) -> Any | ErrorModel | None:
    """OIDC callback

    Args:
        state (str | Unset):
        code (str | Unset):
        conbench_pending (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorModel
    """

    return (
        await asyncio_detailed(
            client=client,
            state=state,
            code=code,
            conbench_pending=conbench_pending,
        )
    ).parsed
