"""remove more unknowns

Revision ID: ab19aaf54876
Revises: b7be3915245e
Create Date: 2021-08-19 18:10:21.177051

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "ab19aaf54876"
down_revision = "b7be3915245e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE commit SET parent = NULL WHERE parent = 'unknown'")
    op.execute("UPDATE commit SET parent = NULL WHERE parent = ''")
    op.execute("UPDATE commit SET repository = '' WHERE repository = 'none'")
    op.execute("UPDATE commit SET sha = '' WHERE sha = 'none'")


def downgrade():
    pass
