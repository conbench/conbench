"""add_history_fingerprint

Revision ID: 9bee3b519bf1
Revises: 167a97c81739
Create Date: 2023-08-29 19:33:34.654753

"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9bee3b519bf1"
down_revision = "167a97c81739"
branch_labels = None
depends_on = None


def upgrade():
    print(f"{datetime.now()} adding column")
    op.add_column(
        "benchmark_result", sa.Column("history_fingerprint", sa.Text(), nullable=True)
    )

    print(f"{datetime.now()} backfilling")
    op.execute(
        """
        UPDATE benchmark_result SET history_fingerprint = MD5(
            benchmark_result.case_id ||
            benchmark_result.context_id ||
            hardware.hash ||
            benchmark_result.commit_repo_url
        )
        FROM hardware
        WHERE benchmark_result.hardware_id = hardware.id
        """
    )

    print(f"{datetime.now()} making non-nullable")
    op.alter_column("benchmark_result", "history_fingerprint", nullable=False)

    print(f"{datetime.now()} creating index")
    op.create_index(
        "benchmark_result_history_fingerprint_index",
        "benchmark_result",
        ["history_fingerprint"],
        unique=False,
    )
    print(f"{datetime.now()} done")


def downgrade():
    op.drop_index(
        "benchmark_result_history_fingerprint_index", table_name="benchmark_result"
    )
    op.drop_column("benchmark_result", "history_fingerprint")
