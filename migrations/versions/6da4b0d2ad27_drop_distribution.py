"""drop distribution

Revision ID: 6da4b0d2ad27
Revises: b7ffcaaeb240
Create Date: 2021-05-11 10:31:22.260237

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6da4b0d2ad27"
down_revision = "b7ffcaaeb240"
branch_labels = None
depends_on = None


def upgrade():
    return
    op.drop_index("distribution_sha_index", table_name="distribution")
    op.drop_index("distribution_repository_index", table_name="distribution")
    op.drop_index("distribution_machine_id_index", table_name="distribution")
    op.drop_index("distribution_index", table_name="distribution")
    op.drop_index("distribution_context_id_index", table_name="distribution")
    op.drop_index("distribution_case_id_index", table_name="distribution")
    op.drop_table("distribution")


def downgrade():
    pass
