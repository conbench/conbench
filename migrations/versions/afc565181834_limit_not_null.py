from alembic import op
import sqlalchemy as sa


revision = "afc565181834"
down_revision = "2d922b652c91"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("distribution", "limit", existing_type=sa.INTEGER(), nullable=False)


def downgrade():
    op.alter_column("distribution", "limit", existing_type=sa.INTEGER(), nullable=True)
