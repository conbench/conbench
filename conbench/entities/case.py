import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import Base, EntityMixin, NotNull, generate_uuid


class Case(Base, EntityMixin):
    __tablename__ = "case"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    # The name of the conceptual benchmark (store on BenchmarkResult directly)?
    name: Mapped[str] = NotNull(s.Text)
    tags: Mapped[dict] = NotNull(postgresql.JSONB)


def get_case_or_create(case_dict) -> Case:
    """
    Try to create case, but expect conflict (work with unique constraint on
    name/tags).

    Return (newly created, or previously existing) Case object, or raise an
    exception.
    """
    try:
        return Case.create(case_dict)
    except s.exc.IntegrityError as exc:
        if "unique constraint" in str(exc):
            # It is known that it exists, otherwise conflict is not precise.
            c = Case.first(**case_dict)
            assert c is not None
            return c
        raise


s.Index("case_index", Case.name, Case.tags, unique=True)
