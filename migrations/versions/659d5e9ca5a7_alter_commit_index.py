"""alter commit index

Revision ID: 659d5e9ca5a7
Revises: fb23ffd732d3
Create Date: 2021-08-19 10:50:53.545163

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "659d5e9ca5a7"
down_revision = "fb23ffd732d3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("commit_index", table_name="commit")
    op.create_index("commit_index", "commit", ["sha", "repository"], unique=True)


def downgrade():
    op.drop_index("commit_index", table_name="commit")
    op.create_index("commit_index", "commit", ["sha"], unique=False)
