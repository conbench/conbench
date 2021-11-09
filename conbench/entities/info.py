import flask as f
import sqlalchemy as s
from sqlalchemy.dialects import postgresql

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    generate_uuid,
)


class Info(Base, EntityMixin):
    __tablename__ = "info"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    tags = NotNull(postgresql.JSONB)


s.Index("info_index", Info.tags, unique=True)


class _Serializer(EntitySerializer):
    def _dump(self, info):
        result = {
            "id": info.id,
            "links": {
                "list": f.url_for("api.infos", _external=True),
                "self": f.url_for("api.info", info_id=info.id, _external=True),
            },
        }
        result.update(info.tags)
        return result


class InfoSerializer:
    one = _Serializer()
    many = _Serializer(many=True)
