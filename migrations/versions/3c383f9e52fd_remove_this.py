"""new

Revision ID: 3c383f9e52fd
Revises: e06cede49f65
Create Date: 2022-03-03 10:39:42.069112

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3c383f9e52fd"
down_revision = "e06cede49f65"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("run", sa.Column("has_errors", sa.Boolean()))
    connection = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=connection)
    run_table = meta.tables["run"]
    connection.execute(run_table.update().values(has_errors=False))
    op.alter_column("run", "has_errors", existing_type=sa.Boolean, nullable=False)


def downgrade():
    op.drop_column("run", "haserrors")
