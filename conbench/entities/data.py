import sqlalchemy as s
from sqlalchemy import CheckConstraint as check

from ..entities._entity import Base, EntityMixin, NotNull, generate_uuid


class Data(Base, EntityMixin):
    __tablename__ = "data"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    summary_id = NotNull(s.String(50), s.ForeignKey("summary.id", ondelete="CASCADE"))
    iteration = NotNull(s.Integer, check("iteration>=1"))
    result = NotNull(s.Numeric, check("result>=0"))


s.Index("data_summary_id_index", Data.summary_id)
