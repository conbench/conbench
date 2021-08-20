"""Drop sha and repository

Revision ID: 847b0850ea81
Revises: c181484ce40f
Create Date: 2021-07-29 11:16:43.377407

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "847b0850ea81"
down_revision = "c181484ce40f"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "distribution", "commit_id", existing_type=sa.VARCHAR(length=50), nullable=False
    )
    op.drop_index("distribution_repository_index", table_name="distribution")
    op.drop_index("distribution_sha_index", table_name="distribution")
    op.drop_index("distribution_index", table_name="distribution")
    op.create_index(
        "distribution_index",
        "distribution",
        ["case_id", "context_id", "commit_id", "machine_hash"],
        unique=True,
    )
    op.drop_column("distribution", "sha")
    op.drop_column("distribution", "repository")


def downgrade():
    op.add_column(
        "distribution",
        sa.Column(
            "repository", sa.VARCHAR(length=100), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "distribution",
        sa.Column("sha", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    )
    op.drop_index("distribution_index", table_name="distribution")
    op.create_index(
        "distribution_index",
        "distribution",
        ["sha", "case_id", "context_id", "machine_hash"],
        unique=False,
    )
    op.create_index("distribution_sha_index", "distribution", ["sha"], unique=False)
    op.create_index(
        "distribution_repository_index", "distribution", ["repository"], unique=False
    )
    op.alter_column(
        "distribution", "commit_id", existing_type=sa.VARCHAR(length=50), nullable=True
    )
