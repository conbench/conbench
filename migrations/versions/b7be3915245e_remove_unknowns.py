"""remove unknowns

Revision ID: b7be3915245e
Revises: 933591271c6a
Create Date: 2021-08-19 17:49:31.661635

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7be3915245e"
down_revision = "933591271c6a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE commit SET author_name = '' WHERE author_name = 'none'")
    op.execute("UPDATE commit SET author_name = '' WHERE author_name = 'unknown'")
    op.execute("UPDATE commit SET message = '' WHERE message = 'none'")
    op.execute("UPDATE commit SET message = '' WHERE message = 'unknown'")


def downgrade():
    pass
