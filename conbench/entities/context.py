from typing import Dict

import flask as f
import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import Base, EntityMixin, EntitySerializer, NotNull, genprimkey


class Context(Base, EntityMixin["Context"]):
    __tablename__ = "context"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=genprimkey)
    tags: Mapped[dict] = NotNull(postgresql.JSONB)

    def to_dict(self) -> Dict:
        """
        Be sure to return `self.tags` directly so that we do not need to keep a
        huge amount of copies of this in memory (this may be shared across many
        benchmark result objects). This here is basically just an indirection
        from the name "tags" to "to_dict()" which I think is more intuitive to
        work with. Think "context dictionary".
        """
        return self.tags


s.Index("context_index", Context.tags, unique=True)


class _Serializer(EntitySerializer):
    def _dump(self, context):
        result = {
            "id": context.id,
            "links": {
                "list": f.url_for("api.contexts", _external=True),
                "self": f.url_for("api.context", context_id=context.id, _external=True),
            },
        }
        result.update(context.tags)
        return result


class ContextSerializer:
    one = _Serializer()
    many = _Serializer(many=True)
