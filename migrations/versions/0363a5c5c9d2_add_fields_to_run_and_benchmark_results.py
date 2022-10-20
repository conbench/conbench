"""add_fields_to_run_and_benchmark_results

Revision ID: 0363a5c5c9d2
Revises: 459166107c9d
Create Date: 2022-10-20 11:14:01.529869

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0363a5c5c9d2"
down_revision = "459166107c9d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "benchmark_result",
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "run", sa.Column("info", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "run",
        sa.Column("error_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("run", sa.Column("error_type", sa.String(length=250), nullable=True))
    op.add_column("run", sa.Column("finished_timestamp", sa.DateTime(), nullable=True))
    op.alter_column(
        "run", "hardware_id", existing_type=sa.VARCHAR(length=50), nullable=True
    )


def downgrade():
    op.alter_column(
        "run", "hardware_id", existing_type=sa.VARCHAR(length=50), nullable=False
    )
    op.drop_column("run", "finished_timestamp")
    op.drop_column("run", "started_at")
    op.drop_column("run", "error_type")
    op.drop_column("run", "error_info")
    op.drop_column("run", "info")
    op.drop_column("benchmark_result", "validation")
