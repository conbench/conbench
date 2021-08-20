"""commit machine index

Revision ID: fb23ffd732d3
Revises: 4ec34b75f4c6
Create Date: 2021-08-09 12:37:56.655438

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "fb23ffd732d3"
down_revision = "4ec34b75f4c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "distribution_commit_machine_index",
        "distribution",
        ["commit_id", "machine_hash"],
        unique=False,
    )


def downgrade():
    op.drop_index("distribution_commit_machine_index", table_name="distribution")
