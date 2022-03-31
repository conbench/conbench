"""Move data and times into summary table

Revision ID: 88040ddc0b08
Revises: e06cede49f65
Create Date: 2022-03-30 16:58:17.412915

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "88040ddc0b08"
down_revision = "e06cede49f65"
branch_labels = None
depends_on = None


def set_data_and_times():
    connection = op.get_bind()
    # meta = sa.MetaData()
    # meta.reflect(bind=connection)
    connection.execute(
        text(
            """UPDATE summary
           SET data = ARRAY(SELECT result FROM data WHERE summary_id = summary.id ORDER BY iteration),
           times = ARRAY(SELECT result FROM "time" WHERE summary_id = summary.id ORDER BY iteration)
        """
        )
    )


def upgrade():
    op.add_column(
        "summary",
        sa.Column(
            "data", postgresql.ARRAY(sa.Numeric()), nullable=True, server_default="{}"
        ),
    )
    op.add_column(
        "summary",
        sa.Column(
            "times", postgresql.ARRAY(sa.Numeric()), nullable=True, server_default="{}"
        ),
    )
    set_data_and_times()


def downgrade():
    op.drop_column("summary", "times")
    op.drop_column("summary", "data")
