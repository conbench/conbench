import dateutil.parser
import sqlalchemy as s

from ..entities._entity import Base, EntityMixin, generate_uuid, NotNull


class GitHub(Base, EntityMixin):
    __tablename__ = "github"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    commit = NotNull(s.String(50))
    repository = NotNull(s.String(100))
    url = NotNull(s.String(250))
    message = NotNull(s.String(250))
    author_name = NotNull(s.String(100))
    author_login = NotNull(s.String(50))
    author_avatar = NotNull(s.String(100))
    timestamp = NotNull(s.DateTime(timezone=False))


def parse_commit(commit):
    return {
        "url": commit["html_url"],
        "date": dateutil.parser.isoparse(commit["commit"]["author"]["date"]),
        "message": commit["commit"]["message"].split("\n")[0],
        "author_name": commit["commit"]["author"]["name"],
        "author_login": commit["author"]["login"],
        "author_avatar": commit["author"]["avatar_url"],
    }
