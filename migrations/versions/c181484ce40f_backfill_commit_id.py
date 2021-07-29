"""Backfill commit id

Revision ID: c181484ce40f
Revises: dc0ed346df63
Create Date: 2021-07-29 08:13:59.714930

"""
from alembic import op
from sqlalchemy import MetaData


# revision identifiers, used by Alembic.
revision = "c181484ce40f"
down_revision = "dc0ed346df63"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)

    commit_table = meta.tables["commit"]
    distribution_table = meta.tables["distribution"]

    commits = connection.execute(commit_table.select())
    distributions = connection.execute(distribution_table.select())
    commits_by_sha = {c["sha"]: c for c in commits}

    i = 1

    for distribution in distributions:
        if distribution.commit_id:
            continue

        commit = commits_by_sha.get(distribution["sha"])
        if not commit:
            print(f"Could not find commit for distribution {distribution.id}")
            continue

        connection.execute(
            distribution_table.update()
            .where(distribution_table.c.id == distribution.id)
            .values(commit_id=commit.id)
        )

        print(f"Updated distribution {1}")
        i += 1

    print("Done with migration")


def downgrade():
    pass
