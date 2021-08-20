"""make parent nullable

Revision ID: d2f09299eb66
Revises: 659d5e9ca5a7
Create Date: 2021-08-19 14:02:07.990221

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d2f09299eb66"
down_revision = "659d5e9ca5a7"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "commit", "parent", existing_type=sa.VARCHAR(length=50), nullable=True
    )


def downgrade():
    op.alter_column(
        "commit", "parent", existing_type=sa.VARCHAR(length=50), nullable=False
    )
