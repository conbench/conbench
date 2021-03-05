import flask as f
import dateutil.parser
import sqlalchemy as s

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    generate_uuid,
    NotNull,
)


class Commit(Base, EntityMixin):
    __tablename__ = "commit"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    sha = NotNull(s.String(50))
    repository = NotNull(s.String(100))
    url = NotNull(s.String(250))
    message = NotNull(s.String(250))
    author_name = NotNull(s.String(100))
    author_login = NotNull(s.String(50))
    author_avatar = NotNull(s.String(100))
    timestamp = NotNull(s.DateTime(timezone=False))


class _Serializer(EntitySerializer):
    def _dump(self, commit):
        return {
            "id": commit.id,
            "sha": commit.sha,
            "repository": commit.repository,
            "url": commit.url,
            "message": commit.message,
            "author_name": commit.author_name,
            "author_login": commit.author_login,
            "author_avatar": commit.author_avatar,
            "timestamp": commit.timestamp.isoformat(),
        }


class CommitSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


def parse_commit(commit):
    return {
        "url": commit["html_url"],
        "date": dateutil.parser.isoparse(commit["commit"]["author"]["date"]),
        "message": commit["commit"]["message"].split("\n")[0],
        "author_name": commit["commit"]["author"]["name"],
        "author_login": commit["author"]["login"],
        "author_avatar": commit["author"]["avatar_url"],
    }
