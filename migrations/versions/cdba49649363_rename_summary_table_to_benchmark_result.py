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
        "ALTER TABLE summary RENAME CONSTRAINT summary_iqr_check TO benchmark_result_iqr_check"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_iterations_check TO benchmark_result_iterations_check"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_max_check TO benchmark_result_max_check"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_mean_check TO benchmark_result_mean_check"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_median_check TO benchmark_result_median_check"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_min_check TO benchmark_result_min_check "
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_pkey TO benchmark_result_pkey"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_q1_check TO benchmark_result_q1_check"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_q3_check TO benchmark_result_q3_check"
    )
    op.execute(
        "ALTER TABLE summary RENAME CONSTRAINT summary_stdev_check TO benchmark_result_stdev_check"
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
    op.rename_table("benchmark_result", "summary")
