import flask as f
import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from conbench.db import Session

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    generate_uuid,
)


class Info(Base, EntityMixin):
    __tablename__ = "info"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    tags: Mapped[dict] = NotNull(postgresql.JSONB)


def get_info_or_create(info_dict) -> Info:
    """
    Try to create, but expect conflict (work with unique constraint on
    name/tags).

    Return (newly created, or previously existing) object, or raise an
    exception.
    """
    try:
        return Info.create(info_dict)
    except s.exc.IntegrityError as exc:
        if "violates unique constraint" not in str(exc):
            raise

    Session.rollback()
    i = Info.first(**info_dict)
    assert i is not None
    return i


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
