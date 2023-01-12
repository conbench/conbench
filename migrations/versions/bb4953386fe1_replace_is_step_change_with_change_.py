"""replace is_step_change with change_annotations

Revision ID: bb4953386fe1
Revises: 498ade3999dd
Create Date: 2023-01-09 13:30:48.860235

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "bb4953386fe1"
down_revision = "498ade3999dd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "benchmark_result",
        sa.Column(
            "change_annotations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.drop_column("benchmark_result", "is_step_change")


def downgrade():
    op.add_column(
        "benchmark_result",
        sa.Column("is_step_change", sa.BOOLEAN(), autoincrement=False, nullable=True),
    )
    op.drop_column("benchmark_result", "change_annotations")
