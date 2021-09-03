"""gpu info

Revision ID: 064a0de5f947
Revises: ab19aaf54876
Create Date: 2021-09-03 11:00:08.205984

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "064a0de5f947"
down_revision = "ab19aaf54876"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("machine", sa.Column("gpu_count", sa.Integer(), nullable=True))
    op.add_column(
        "machine",
        sa.Column("gpu_product_names", postgresql.ARRAY(sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("machine", "gpu_product_names")
    op.drop_column("machine", "gpu_count")
