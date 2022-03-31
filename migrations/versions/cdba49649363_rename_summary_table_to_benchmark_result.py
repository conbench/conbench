"""Rename summary table to benchmark_result

Revision ID: cdba49649363
Revises: 4fb49a9299a2
Create Date: 2022-03-31 13:39:47.877909

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "cdba49649363"
down_revision = "4fb49a9299a2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_case_id_fkey TO benchmark_result_case_id_fkey"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_context_id_fkey TO benchmark_result_context_id_fkey"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_info_id_fkey TO benchmark_result_info_id_fkey"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_run_id_fkey TO benchmark_result_run_id_fkey"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_pkey TO benchmark_result_pkey"
    )
    op.execute(
        "ALTER INDEX summary_batch_id_index RENAME TO benchmark_result_batch_id_index"
    )
    op.execute(
        "ALTER INDEX summary_case_id_index RENAME TO benchmark_result_case_id_index"
    )
    op.execute(
        "ALTER INDEX summary_context_id_index RENAME TO benchmark_result_context_id_index"
    )
    op.execute(
        "ALTER INDEX summary_info_id_index RENAME TO benchmark_result_info_id_index"
    )
    op.execute(
        "ALTER INDEX summary_run_id_index RENAME TO benchmark_result_run_id_index"
    )
    op.rename_table("summary", "benchmark_result")


def downgrade():
    op.execute(
        "ALTER TABLE benchmark_result RENAME CONSTRAINT benchmark_result_case_id_fkey TO summary_case_id_fkey"
    )
    op.execute(
        "ALTER TABLE benchmark_result RENAME CONSTRAINT benchmark_result_context_id_fkey TO summary_context_id_fkey"
    )
    op.execute(
        "ALTER TABLE benchmark_result RENAME CONSTRAINT benchmark_result_info_id_fkey TO summary_info_id_fkey"
    )
    op.execute(
        "ALTER TABLE benchmark_result RENAME CONSTRAINT benchmark_result_run_id_fkey TO summary_run_id_fkey"
    )
    op.execute(
        "ALTER TABLE benchmark_result RENAME CONSTRAINT benchmark_result_pkey TO summary_pkey"
    )
    op.execute(
        "ALTER INDEX benchmark_result_batch_id_index RENAME TO summary_batch_id_index"
    )
    op.execute(
        "ALTER INDEX benchmark_result_case_id_index RENAME TO summary_case_id_index"
    )
    op.execute(
        "ALTER INDEX benchmark_result_context_id_index RENAME TO summary_context_id_index"
    )
    op.execute(
        "ALTER INDEX benchmark_result_info_id_index RENAME TO summary_info_id_index"
    )
    op.execute(
        "ALTER INDEX benchmark_result_run_id_index RENAME TO summary_run_id_index"
    )
    op.rename_table("benchmark_result", "summary")
