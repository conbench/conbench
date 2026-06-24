"""Conbench Python SDK public package exports."""

from __future__ import annotations

from typing import Any

__all__ = (
    "AuthenticatedClient",
    "Client",
)


def __getattr__(name: str) -> Any:
    if name == "AuthenticatedClient":
        from .client import AuthenticatedClient

        return AuthenticatedClient
    if name == "Client":
        from .client import Client

        return Client
    raise AttributeError(f"module 'conbench' has no attribute {name!r}")
