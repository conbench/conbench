"""big_arrow_migration

Revision ID: 9bee3b519bf1
Revises: dd6597846acf
Create Date: 2023-09-14 19:48:41.642794

"""
import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9bee3b519bf1"
down_revision = "dd6597846acf"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)


def upgrade():
    log.info("creating temp table")
    op.execute(
        """
        CREATE TABLE temp AS
        WITH result AS (
            SELECT
                benchmark_result.*,
                jsonb_build_object('name', coalesce(run.name, '')) AS run_tags,
                run.reason AS run_reason,
                run.commit_id AS commit_id,
                run.hardware_id AS hardware_id,
                COALESCE(commit.repository, 'https://github.com/apache/arrow') AS commit_repo_url
            FROM benchmark_result
            LEFT JOIN run ON run.id = benchmark_result.run_id
            LEFT JOIN commit ON commit.id = run.commit_id
        )
        SELECT
            result.*,
            MD5(
                result.case_id ||
                result.context_id ||
                hardware.hash ||
                result.commit_repo_url
            ) AS history_fingerprint
        FROM result
        LEFT JOIN hardware ON hardware.id = result.hardware_id
        """
    )

    log.info("dropping benchmark_result table")
    op.drop_table("benchmark_result")

    log.info("dropping run table")
    op.drop_table("run")

    log.info("renaming temp table")
    op.execute("ALTER TABLE temp RENAME TO benchmark_result")

    log.info("marking id as primary key")
    op.execute("ALTER TABLE benchmark_result ADD PRIMARY KEY (id)")

    log.info("-- making columns non-nullable --")
    for colname in [
        "case_id",
        "info_id",
        "context_id",
        "run_id",
        "run_tags",
        "commit_repo_url",
        "hardware_id",
        "history_fingerprint",
        "timestamp",
    ]:
        log.info(colname)
        op.alter_column("benchmark_result", colname, nullable=False)

    log.info("-- recreating indexes --")
    for colname in [
        "batch_id",
        "case_id",
        "context_id",
        "history_fingerprint",
        "info_id",
        "run_id",
        "timestamp",
        "commit_id",
    ]:
        log.info(colname)
        op.create_index(
            f"benchmark_result_{colname}_index", "benchmark_result", [colname]
        )

    log.info("-- recreating foreign keys --")
    for tablename in ["hardware", "commit", "case", "info", "context"]:
        log.info(tablename)
        op.create_foreign_key(
            None,
            "benchmark_result",
            tablename,
            [f"{tablename}_id"],
            ["id"],
        )

    log.info("done")


def downgrade():
    op.drop_constraint(None, "benchmark_result", type_="foreignkey")
    op.drop_constraint(None, "benchmark_result", type_="foreignkey")
    op.create_foreign_key(
        "benchmark_result_run_id_fkey", "benchmark_result", "run", ["run_id"], ["id"]
    )
    op.drop_index(
        "benchmark_result_history_fingerprint_index", table_name="benchmark_result"
    )
    op.drop_index("benchmark_result_commit_id_index", table_name="benchmark_result")
    op.drop_column("benchmark_result", "history_fingerprint")
    op.drop_column("benchmark_result", "hardware_id")
    op.drop_column("benchmark_result", "commit_repo_url")
    op.drop_column("benchmark_result", "commit_id")
    op.drop_column("benchmark_result", "run_reason")
    op.drop_column("benchmark_result", "run_tags")
    op.create_table(
        "run",
        sa.Column("id", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
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
        sa.Column("name", sa.VARCHAR(length=250), autoincrement=False, nullable=True),
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
