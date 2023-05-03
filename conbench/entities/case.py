import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import Base, EntityMixin, NotNull, genprimkey


class Case(Base, EntityMixin["Case"]):
    # __slots__ = ("id", "name", "tags")

    __tablename__ = "case"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=genprimkey)
    # The name of the conceptual benchmark (store on BenchmarkResult directly)?
    name: Mapped[str] = NotNull(s.Text)
    tags: Mapped[dict] = NotNull(postgresql.JSONB)


s.Index("case_index", Case.name, Case.tags, unique=True)
