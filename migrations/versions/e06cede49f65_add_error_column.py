"""add_error_column

Revision ID: e06cede49f65
Revises: aa5092d7e206
Create Date: 2022-03-02 14:11:15.615473

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e06cede49f65"
down_revision = "aa5092d7e206"
branch_labels = None
depends_on = None


def set_run_has_errors_values():
    connection = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=connection)
    run_table = meta.tables["run"]
    connection.execute(run_table.update().values(has_errors=False))


def upgrade():
    op.add_column(
        "summary",
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.alter_column(
        "machine", "hash", existing_type=sa.VARCHAR(length=1000), nullable=False
    )
    op.alter_column("summary", "unit", existing_type=sa.TEXT(), nullable=True)
    op.alter_column("summary", "time_unit", existing_type=sa.TEXT(), nullable=True)
    op.alter_column("summary", "batch_id", existing_type=sa.TEXT(), nullable=True)
    op.alter_column("summary", "iterations", existing_type=sa.INTEGER(), nullable=True)
    op.add_column("run", sa.Column("has_errors", sa.Boolean()))
    set_run_has_errors_values()
    op.alter_column("run", "has_errors", existing_type=sa.Boolean, nullable=False)


def downgrade():
    op.drop_column("run", "has_errors")
    op.alter_column("summary", "iterations", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column("summary", "batch_id", existing_type=sa.TEXT(), nullable=False)
    op.alter_column("summary", "time_unit", existing_type=sa.TEXT(), nullable=False)
    op.alter_column("summary", "unit", existing_type=sa.TEXT(), nullable=False)
    op.alter_column(
        "machine", "hash", existing_type=sa.VARCHAR(length=1000), nullable=True
    )
    op.drop_column("summary", "error")
