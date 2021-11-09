"""info table

Revision ID: 3ddd66ca34f2
Revises: 8a72866f991c
Create Date: 2021-11-10 14:07:47.220030

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3ddd66ca34f2"
down_revision = "8a72866f991c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "info",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("info_index", "info", ["tags"], unique=True)
    op.add_column("summary", sa.Column("info_id", sa.String(length=50), nullable=True))
    op.create_foreign_key(
        "summary_info_id_fkey", "summary", "info", ["info_id"], ["id"]
    )
    op.create_index("summary_context_id_index", "summary", ["context_id"], unique=False)
    op.create_index("summary_info_id_index", "summary", ["info_id"], unique=False)


def downgrade():
    op.drop_constraint("summary_info_id_fkey", "summary", type_="foreignkey")
    op.drop_index("summary_info_id_index", table_name="summary")
    op.drop_index("summary_context_id_index", table_name="summary")
    op.drop_column("summary", "info_id")
    op.drop_index("info_index", table_name="info")
    op.drop_table("info")
