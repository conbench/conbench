import sqlalchemy as s
from sqlalchemy.dialects import postgresql

from ..entities._entity import Base, EntityMixin, NotNull, generate_uuid


class Case(Base, EntityMixin):
    __tablename__ = "case"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    name = NotNull(s.Text)
    tags = NotNull(postgresql.JSONB)


s.Index("case_index", Case.name, Case.tags, unique=True)
