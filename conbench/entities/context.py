import flask as f
import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    generate_uuid,
)


class Context(Base, EntityMixin):
    __tablename__ = "context"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    tags: Mapped[dict] = NotNull(postgresql.JSONB)


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
