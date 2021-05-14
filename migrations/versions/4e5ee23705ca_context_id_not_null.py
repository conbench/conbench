from alembic import op
import sqlalchemy as sa


revision = "4e5ee23705ca"
down_revision = "de31ab708b6c"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "run", "context_id", existing_type=sa.VARCHAR(length=50), nullable=False
    )


def downgrade():
    op.alter_column(
        "run", "context_id", existing_type=sa.VARCHAR(length=50), nullable=True
    )
