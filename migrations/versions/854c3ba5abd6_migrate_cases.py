"""migrate cases

Revision ID: 854c3ba5abd6
Revises: 991493b6406a
Create Date: 2021-04-08 08:45:38.935858

"""
from alembic import op
from sqlalchemy import update

from conbench.entities.case import Case
from conbench.entities.summary import Summary
from conbench.db import Session


# revision identifiers, used by Alembic.
revision = "854c3ba5abd6"
down_revision = "991493b6406a"
branch_labels = None
depends_on = None


def upgrade():
    cases = Case.all()
    for case in cases:
        if "gc_collect" in case.tags or "gc_disable" in case.tags:
            new_tags = dict(case.tags)
            new_tags.pop("gc_collect")
            new_tags.pop("gc_disable")
            c = {"name": case.name, "tags": new_tags}
            other = Case.first(**c)
            if other:
                stmt = (
                    update(Summary)
                    .where(Summary.case_id == case.id)
                    .values(case_id=other.id)
                    .execution_options(synchronize_session="fetch")
                )
                Session.execute(stmt)
                case.delete()


def downgrade():
    pass
