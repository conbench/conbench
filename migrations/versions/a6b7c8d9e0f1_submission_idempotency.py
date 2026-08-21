"""submission_idempotency

Revision ID: a6b7c8d9e0f1
Revises: 9d5f3c1a7b2e
Create Date: 2026-08-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a6b7c8d9e0f1"
down_revision = "9d5f3c1a7b2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("benchmark_result", sa.Column("submission_key", sa.Text(), nullable=True))
    op.add_column(
        "benchmark_result",
        sa.Column("submission_payload_sha256", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "benchmark_result_submission_idempotency_check",
        "benchmark_result",
        "(submission_key IS NULL AND submission_payload_sha256 IS NULL) OR "
        "(submission_key IS NOT NULL AND submission_payload_sha256 ~ '^[0-9a-f]{64}$')",
        postgresql_not_valid=True,
    )
    with op.get_context().autocommit_block():
        op.create_index(
            "benchmark_result_submission_key_index",
            "benchmark_result",
            ["submission_key"],
            unique=True,
            postgresql_concurrently=True,
            postgresql_where=sa.text("submission_key IS NOT NULL"),
        )
    op.execute(
        "ALTER TABLE benchmark_result VALIDATE CONSTRAINT "
        "benchmark_result_submission_idempotency_check"
    )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "benchmark_result_submission_key_index",
            table_name="benchmark_result",
            postgresql_concurrently=True,
        )
    op.drop_constraint(
        "benchmark_result_submission_idempotency_check",
        "benchmark_result",
        type_="check",
    )
    op.drop_column("benchmark_result", "submission_payload_sha256")
    op.drop_column("benchmark_result", "submission_key")
