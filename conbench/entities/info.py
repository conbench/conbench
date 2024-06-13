import flask as f
import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import Base, EntityMixin, EntitySerializer, NotNull, genprimkey


class Info(Base, EntityMixin["Info"]):
    __tablename__ = "info"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=genprimkey)
    tags: Mapped[dict] = NotNull(postgresql.JSONB)


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
