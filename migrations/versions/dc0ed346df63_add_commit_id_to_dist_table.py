"""Add commit id to dist table

Revision ID: dc0ed346df63
Revises: 69493ddc938a
Create Date: 2021-07-28 08:50:54.190008

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "dc0ed346df63"
down_revision = "69493ddc938a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "distribution", sa.Column("commit_id", sa.String(length=50), nullable=True)
    )
    op.create_index(
        "distribution_commit_id_index", "distribution", ["commit_id"], unique=False
    )
    op.create_foreign_key(
        None, "distribution", "commit", ["commit_id"], ["id"], ondelete="CASCADE"
    )


def downgrade():
    op.drop_constraint(None, "distribution", type_="foreignkey")
    op.drop_index("distribution_commit_id_index", table_name="distribution")
    op.drop_column("distribution", "commit_id")
