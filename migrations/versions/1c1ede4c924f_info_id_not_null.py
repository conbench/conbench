"""info id not null

Revision ID: 1c1ede4c924f
Revises: 1fed559406c5
Create Date: 2021-11-17 10:03:27.286293

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1c1ede4c924f"
down_revision = "1fed559406c5"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "summary", "info_id", existing_type=sa.VARCHAR(length=50), nullable=False
    )


def downgrade():
    op.alter_column(
        "summary", "info_id", existing_type=sa.VARCHAR(length=50), nullable=True
    )
