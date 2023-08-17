"""remove_run_table

Revision ID: 2ee66194b9eb
Revises: dd6597846acf
Create Date: 2023-08-17 19:21:44.094129

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2ee66194b9eb"
down_revision = "dd6597846acf"
branch_labels = None
depends_on = None


def upgrade():
    # TODO: data migration from run to benchmark_result goes here!

    op.add_column(
        "benchmark_result",
        sa.Column("run_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.add_column("benchmark_result", sa.Column("run_reason", sa.Text(), nullable=True))
    op.add_column(
        "benchmark_result", sa.Column("commit_id", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "benchmark_result",
        sa.Column("hardware_id", sa.String(length=50), nullable=False),
    )
    op.drop_constraint("summary_run_id_fkey", "benchmark_result", type_="foreignkey")
    op.create_foreign_key(None, "benchmark_result", "hardware", ["hardware_id"], ["id"])
    op.create_foreign_key(None, "benchmark_result", "commit", ["commit_id"], ["id"])

    op.drop_table("run")


def downgrade():
    op.drop_constraint(None, "benchmark_result", type_="foreignkey")
    op.drop_constraint(None, "benchmark_result", type_="foreignkey")
    op.create_foreign_key(
        "summary_run_id_fkey", "benchmark_result", "run", ["run_id"], ["id"]
    )
    op.drop_column("benchmark_result", "hardware_id")
    op.drop_column("benchmark_result", "commit_id")
    op.drop_column("benchmark_result", "run_reason")
    op.drop_column("benchmark_result", "run_tags")
    op.create_table(
        "run",
        sa.Column("id", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=250), autoincrement=False, nullable=True),
        sa.Column(
            "timestamp",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "commit_id", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "hardware_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
        sa.Column(
            "has_errors",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("reason", sa.VARCHAR(length=250), autoincrement=False, nullable=True),
        sa.Column(
            "info",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "error_info",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "error_type", sa.VARCHAR(length=250), autoincrement=False, nullable=True
        ),
        sa.Column(
            "finished_timestamp",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["commit_id"], ["commit.id"], name="run_commit_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["hardware_id"], ["hardware.id"], name="run_hardware_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="run_pkey"),
    )
