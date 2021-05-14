import os

from alembic import op
import requests
from sqlalchemy import MetaData


revision = "662175f2e6c6"
down_revision = "782f4533db71"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    commit_table = meta.tables["commit"]

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
