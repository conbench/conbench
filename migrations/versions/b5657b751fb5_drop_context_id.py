"""drop context_id

Revision ID: b5657b751fb5
Revises: 4e5ee23705ca
Create Date: 2021-04-26 15:23:17.012335

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5657b751fb5"
down_revision = "4e5ee23705ca"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("run_context_id_fkey", "run", type_="foreignkey")
    op.drop_column("run", "context_id")


def downgrade():
    op.add_column(
        "run",
        sa.Column(
            "context_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
    )
    op.create_foreign_key(
        "run_context_id_fkey", "run", "context", ["context_id"], ["id"]
    )
