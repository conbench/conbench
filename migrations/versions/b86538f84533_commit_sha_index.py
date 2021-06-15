from alembic import op


revision = "b86538f84533"
down_revision = "bb5acca23f97"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("commit_index", "commit", ["sha"], unique=True)


def downgrade():
    op.drop_index("commit_index", table_name="commit")
