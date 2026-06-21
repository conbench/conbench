from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...models.capabilities_output_body import CapabilitiesOutputBody
from ...models.error_model import ErrorModel
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    conbench_session: str | Unset = UNSET,
) -> dict[str, Any]:

    cookies = {}
    if conbench_session is not UNSET:
        cookies["conbench_session"] = conbench_session

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/auth/capabilities",
        "cookies": cookies,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CapabilitiesOutputBody | ErrorModel:
    if response.status_code == 200:
        response_200 = CapabilitiesOutputBody.from_dict(response.json())

        return response_200

    response_default = ErrorModel.from_dict(response.json())

    return response_default


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CapabilitiesOutputBody | ErrorModel]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    conbench_session: str | Unset = UNSET,
) -> Response[CapabilitiesOutputBody | ErrorModel]:
    """Browser-visible auth capabilities

    Args:
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CapabilitiesOutputBody | ErrorModel]
    """

    kwargs = _get_kwargs(
        conbench_session=conbench_session,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    conbench_session: str | Unset = UNSET,
) -> CapabilitiesOutputBody | ErrorModel | None:
    """Browser-visible auth capabilities

    Args:
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CapabilitiesOutputBody | ErrorModel
    """

    return sync_detailed(
        client=client,
        conbench_session=conbench_session,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    conbench_session: str | Unset = UNSET,
) -> Response[CapabilitiesOutputBody | ErrorModel]:
    """Browser-visible auth capabilities

    Args:
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CapabilitiesOutputBody | ErrorModel]
    """

    kwargs = _get_kwargs(
        conbench_session=conbench_session,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    conbench_session: str | Unset = UNSET,
) -> CapabilitiesOutputBody | ErrorModel | None:
    """Browser-visible auth capabilities

    Args:
        conbench_session (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CapabilitiesOutputBody | ErrorModel
    """

    return (
        await asyncio_detailed(
            client=client,
            conbench_session=conbench_session,
        )
    ).parsed
