"""add run reason column

Revision ID: bc0ac747cec6
Revises: 5d516a1f293d
Create Date: 2022-06-07 15:21:28.698451

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bc0ac747cec6"
down_revision = "5d516a1f293d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("run", sa.Column("reason", sa.String(length=250), nullable=True))


def downgrade():
    op.drop_column("run", "reason")
