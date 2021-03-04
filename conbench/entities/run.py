import sqlalchemy as s
from sqlalchemy.orm import relationship

from ..entities._entity import Base, EntityMixin, NotNull


class Run(Base, EntityMixin):
    __tablename__ = "run"
    id = NotNull(s.String(50), primary_key=True)
    timestamp = NotNull(s.DateTime(timezone=False), server_default=s.sql.func.now())
    github_id = NotNull(s.String(50), s.ForeignKey("github.id"))
    github = relationship("GitHub", lazy="joined")
