from alembic import op
import sqlalchemy as sa


revision = "782f4533db71"
down_revision = "854c3ba5abd6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("commit", sa.Column("parent", sa.String(length=50), nullable=True))
    op.drop_column("commit", "url")


def downgrade():
    op.add_column(
        "commit",
        sa.Column("url", sa.VARCHAR(length=250), autoincrement=False, nullable=False),
    )
    op.drop_column("commit", "parent")
