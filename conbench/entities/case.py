from typing import Dict

import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import Base, EntityMixin, NotNull, genprimkey


class Case(Base, EntityMixin["Case"]):
    __tablename__ = "case"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=genprimkey)
    # The name of the conceptual benchmark (store on BenchmarkResult directly)?
    name: Mapped[str] = NotNull(s.Text)

    # Note(JP): we should work towards guaranteeing str->str mapping
    tags: Mapped[dict] = NotNull(postgresql.JSONB)

    def to_dict(self) -> Dict:
        """
        Be sure to return `self.tags` directly so that we do not need to keep a
        huge amount of copies of this in memory (this may be shared across many
        benchmark result objects). This here is basically just an indirection
        from the name "tags" to "to_dict()" which I think is more intuitive to
        work with. Think "case dictionary".
        """
        return self.tags


s.Index("case_index", Case.name, Case.tags, unique=True)
