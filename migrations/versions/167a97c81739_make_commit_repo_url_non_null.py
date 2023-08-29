"""make_commit_repo_url_non_null

Revision ID: 167a97c81739
Revises: afe717e97b78
Create Date: 2023-08-28 19:30:41.882672

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "167a97c81739"
down_revision = "afe717e97b78"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "benchmark_result", "commit_repo_url", existing_type=sa.TEXT(), nullable=False
    )


def downgrade():
    op.alter_column(
        "benchmark_result", "commit_repo_url", existing_type=sa.TEXT(), nullable=True
    )
