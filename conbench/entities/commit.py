import dateutil.parser
import sqlalchemy as s

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    generate_uuid,
    NotNull,
    Nullable,
)


class Commit(Base, EntityMixin):
    __tablename__ = "commit"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    sha = NotNull(s.String(50))
    parent = NotNull(s.String(50))
    repository = NotNull(s.String(100))
    message = NotNull(s.String(250))
    author_name = NotNull(s.String(100))
    author_login = Nullable(s.String(50))
    author_avatar = Nullable(s.String(100))
    timestamp = NotNull(s.DateTime(timezone=False))


s.Index(
    "commit_index",
    Commit.sha,
    unique=True,
)


class _Serializer(EntitySerializer):
    def _dump(self, commit):
        return {
            "id": commit.id,
            "sha": commit.sha,
            "url": f"{commit.repository}/commit/{commit.sha}",
            "parent_sha": commit.parent,
            "parent_url": f"{commit.repository}/commit/{commit.parent}",
            "repository": commit.repository,
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
        "parent": commit["parents"][0]["sha"],
        "date": dateutil.parser.isoparse(commit["commit"]["author"]["date"]),
        "message": commit["commit"]["message"].split("\n")[0],
        "author_name": commit["commit"]["author"]["name"],
        "author_login": commit["author"]["login"] if commit["author"] else None,
        "author_avatar": commit["author"]["avatar_url"] if commit["author"] else None,
    }
