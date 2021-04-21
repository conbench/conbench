"""backfill parent

Revision ID: 662175f2e6c6
Revises: 782f4533db71
Create Date: 2021-04-21 09:23:28.589522

"""
import os

from alembic import op
import requests


from conbench.entities.commit import Commit


# revision identifiers, used by Alembic.
revision = "662175f2e6c6"
down_revision = "782f4533db71"
branch_labels = None
depends_on = None


def upgrade():
    commit_table = Commit.__table__
    connection = op.get_bind()

    token, session = os.getenv("GITHUB_API_TOKEN"), None
    if token:
        session = requests.Session()
        session.headers = {"Authorization": f"Bearer {token}"}

    commits = connection.execute(
        commit_table.select().where(commit_table.c.parent == None)  # noqa
    )

    for commit in commits:
        url = f"https://api.github.com/repos/apache/arrow/commits/{commit.sha}"
        response = session.get(url) if session else requests.get(url)
        parent = response.json()["parents"][0]["sha"]
        connection.execute(
            commit_table.update()
            .where(commit_table.c.sha == commit.sha)
            .values(parent=parent)
        )


def downgrade():
    pass
