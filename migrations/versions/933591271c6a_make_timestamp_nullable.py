"""make timestamp nullable

Revision ID: 933591271c6a
Revises: d2f09299eb66
Create Date: 2021-08-19 15:19:11.396669

"""
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "933591271c6a"
down_revision = "d2f09299eb66"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "commit", "timestamp", existing_type=postgresql.TIMESTAMP(), nullable=True
    )


def downgrade():
    op.alter_column(
        "commit", "timestamp", existing_type=postgresql.TIMESTAMP(), nullable=False
    )
