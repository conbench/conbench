"""add_result_repo_col

Revision ID: afe717e97b78
Revises: 2ee66194b9eb
Create Date: 2023-08-24 15:21:19.938993

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "afe717e97b78"
down_revision = "2ee66194b9eb"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "benchmark_result", sa.Column("commit_repo_url", sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column("benchmark_result", "commit_repo_url")
