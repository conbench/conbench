"""commit sha index

Revision ID: b86538f84533
Revises: bb5acca23f97
Create Date: 2021-04-21 13:35:38.613978

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b86538f84533"
down_revision = "bb5acca23f97"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("commit_index", "commit", ["sha"], unique=True)


def downgrade():
    op.drop_index("commit_index", table_name="commit")
