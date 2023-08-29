"""add_history_fingerprint

Revision ID: 9bee3b519bf1
Revises: 167a97c81739
Create Date: 2023-08-29 19:33:34.654753

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9bee3b519bf1"
down_revision = "167a97c81739"
branch_labels = None
depends_on = None


def upgrade():
    # TODO before I merge this PR: fix this migration code!!

    op.add_column(
        "benchmark_result", sa.Column("history_fingerprint", sa.Text(), nullable=False)
    )
    op.create_index(
        "benchmark_result_history_fingerprint_index",
        "benchmark_result",
        ["history_fingerprint"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "benchmark_result_history_fingerprint_index", table_name="benchmark_result"
    )
    op.drop_column("benchmark_result", "history_fingerprint")
