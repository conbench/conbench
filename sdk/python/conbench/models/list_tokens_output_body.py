from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.token_view import TokenView


T = TypeVar("T", bound="ListTokensOutputBody")


@_attrs_define
class ListTokensOutputBody:
    """
    Attributes:
        tokens (list[TokenView] | None):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    tokens: list[TokenView] | None
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        tokens: list[dict[str, Any]] | None
        if isinstance(self.tokens, list):
            tokens = []
            for tokens_type_0_item_data in self.tokens:
                tokens_type_0_item = tokens_type_0_item_data.to_dict()
                tokens.append(tokens_type_0_item)

        else:
            tokens = self.tokens

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "tokens": tokens,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.token_view import TokenView

        d = dict(src_dict)

        def _parse_tokens(data: object) -> list[TokenView] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                tokens_type_0 = []
                _tokens_type_0 = data
                for tokens_type_0_item_data in _tokens_type_0:
                    tokens_type_0_item = TokenView.from_dict(tokens_type_0_item_data)

                    tokens_type_0.append(tokens_type_0_item)

                return tokens_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[TokenView] | None, data)

        tokens = _parse_tokens(d.pop("tokens"))

        schema = d.pop("$schema", UNSET)

        list_tokens_output_body = cls(
            tokens=tokens,
            schema=schema,
        )

        return list_tokens_output_body
