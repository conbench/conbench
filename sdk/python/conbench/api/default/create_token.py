from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.create_token_input_body import CreateTokenInputBody
from ...models.create_token_output_body import CreateTokenOutputBody
from ...models.error_model import ErrorModel
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: CreateTokenInputBody,
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
        "method": "post",
        "url": "/api/tokens",
        "cookies": cookies,
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CreateTokenOutputBody | ErrorModel:
    if response.status_code == 201:
        response_201 = CreateTokenOutputBody.from_dict(response.json())

        return response_201

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CreateTokenOutputBody | ErrorModel]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateTokenInputBody,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[CreateTokenOutputBody | ErrorModel]:
    """Mint an API token

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):
        body (CreateTokenInputBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateTokenOutputBody | ErrorModel]
    """

    kwargs = _get_kwargs(
        body=body,
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
    body: CreateTokenInputBody,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> CreateTokenOutputBody | ErrorModel | None:
    """Mint an API token

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):
        body (CreateTokenInputBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateTokenOutputBody | ErrorModel
    """

    return sync_detailed(
        client=client,
        body=body,
        authorization=authorization,
        conbench_session=conbench_session,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateTokenInputBody,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> Response[CreateTokenOutputBody | ErrorModel]:
    """Mint an API token

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):
        body (CreateTokenInputBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateTokenOutputBody | ErrorModel]
    """

    kwargs = _get_kwargs(
        body=body,
        authorization=authorization,
        conbench_session=conbench_session,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateTokenInputBody,
    authorization: str | Unset = UNSET,
    conbench_session: str | Unset = UNSET,
) -> CreateTokenOutputBody | ErrorModel | None:
    """Mint an API token

    Args:
        authorization (str | Unset): Bearer token.
        conbench_session (str | Unset):
        body (CreateTokenInputBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateTokenOutputBody | ErrorModel
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            authorization=authorization,
            conbench_session=conbench_session,
        )
    ).parsed
