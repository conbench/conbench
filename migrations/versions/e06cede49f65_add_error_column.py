"""add_error_column

Revision ID: e06cede49f65
Revises: aa5092d7e206
Create Date: 2022-03-02 14:11:15.615473

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e06cede49f65"
down_revision = "aa5092d7e206"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "summary",
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("summary", "error")
