"""drop machine id

Revision ID: 69493ddc938a
Revises: afc565181834
Create Date: 2021-06-15 15:12:07.013039

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "69493ddc938a"
down_revision = "afc565181834"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("summary_machine_id_fkey", "summary", type_="foreignkey")
    op.drop_column("summary", "machine_id")


def downgrade():
    op.add_column(
        "summary",
        sa.Column(
            "machine_id", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
    )
    op.create_foreign_key(
        "summary_machine_id_fkey", "summary", "machine", ["machine_id"], ["id"]
    )
