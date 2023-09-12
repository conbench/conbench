"""add_history_fingerprint

Revision ID: 9bee3b519bf1
Revises: 167a97c81739
Create Date: 2023-08-29 19:33:34.654753

"""
from datetime import datetime

from alembic import op


def p(msg):
    # I couldn't get logging to work quickly.
    print(f"[{datetime.now().isoformat()}] {msg}")


# revision identifiers, used by Alembic.
revision = "9bee3b519bf1"
down_revision = "167a97c81739"
branch_labels = None
depends_on = None


def upgrade():
    # This backfill is large and expensive so let's use the "create table as select"
    # strategy. I validated that the MD5(...) function in a Postgres DB produces the
    # same result as the python generate_history_fingerprint() function.
    p("creating temp table")
    op.execute(
        """
        CREATE TABLE temp AS
        SELECT
            benchmark_result.*,
            MD5(
                benchmark_result.case_id ||
                benchmark_result.context_id ||
                hardware.hash ||
                benchmark_result.commit_repo_url
            ) AS history_fingerprint
        FROM benchmark_result
        LEFT JOIN hardware ON benchmark_result.hardware_id = hardware.id
        """
    )

    p("dropping old table")
    op.execute("DROP TABLE benchmark_result")

    p("renaming temp table")
    op.execute("ALTER TABLE temp RENAME TO benchmark_result")

    p("marking id as primary key")
    op.execute("ALTER TABLE benchmark_result ADD PRIMARY KEY (id)")

    p("-- making columns non-nullable --")
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
        p(colname)
        op.alter_column("benchmark_result", colname, nullable=False)

    p("-- recreating indexes --")
    for colname in [
        "batch_id",
        "case_id",
        "context_id",
        "history_fingerprint",
        "info_id",
        "run_id",
        "timestamp",
    ]:
        p(colname)
        op.create_index(
            f"benchmark_result_{colname}_index", "benchmark_result", [colname]
        )

    p("-- recreating foreign keys --")
    for tablename in ["hardware", "commit", "case", "info", "context"]:
        p(tablename)
        op.create_foreign_key(
            None,
            "benchmark_result",
            tablename,
            [f"{tablename}_id"],
            ["id"],
        )

    p("done")


def downgrade():
    op.drop_index(
        "benchmark_result_history_fingerprint_index", table_name="benchmark_result"
    )
    op.drop_column("benchmark_result", "history_fingerprint")
