"""Drop single indexes

Revision ID: 4ec34b75f4c6
Revises: 847b0850ea81
Create Date: 2021-07-29 19:03:32.232337

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "4ec34b75f4c6"
down_revision = "847b0850ea81"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("distribution_case_id_index", table_name="distribution")
    op.drop_index("distribution_commit_id_index", table_name="distribution")
    op.drop_index("distribution_context_id_index", table_name="distribution")
    op.drop_index("distribution_machine_hash_index", table_name="distribution")


def downgrade():
    op.create_index(
        "distribution_machine_hash_index",
        "distribution",
        ["machine_hash"],
        unique=False,
    )
    op.create_index(
        "distribution_context_id_index", "distribution", ["context_id"], unique=False
    )
    op.create_index(
        "distribution_commit_id_index", "distribution", ["commit_id"], unique=False
    )
    op.create_index(
        "distribution_case_id_index", "distribution", ["case_id"], unique=False
    )
