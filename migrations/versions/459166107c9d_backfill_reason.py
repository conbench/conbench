"""backfill reason

Revision ID: 459166107c9d
Revises: bc0ac747cec6
Create Date: 2022-06-10 09:49:05.883111

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "459166107c9d"
down_revision = "bc0ac747cec6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE run SET reason = 'nightly'
        WHERE reason IS NULL AND name LIKE '%nightly';
        """
    )
    op.execute(
        """
        UPDATE run SET reason = 'commit'
        WHERE reason IS NULL AND name LIKE 'commit%';
        """
    )
    op.execute(
        """
        UPDATE run SET reason = 'pull request'
        WHERE reason IS NULL AND name LIKE 'pull request%';
        """
    )
    op.execute(
        """
        UPDATE run SET reason = 'manual'
        WHERE reason IS NULL AND name LIKE 'manual%';
        """
    )
    op.execute(
        """
        UPDATE run SET reason = 'manual'
        WHERE reason IS NULL AND name LIKE 'test%';
        """
    )


def downgrade():
    pass
