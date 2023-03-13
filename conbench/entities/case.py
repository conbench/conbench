import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import Base, EntityMixin, NotNull, generate_uuid


class Case(Base, EntityMixin):
    __tablename__ = "case"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    name: Mapped[str] = NotNull(s.Text)
    tags: Mapped[dict] = NotNull(postgresql.JSONB)


s.Index("case_index", Case.name, Case.tags, unique=True)
