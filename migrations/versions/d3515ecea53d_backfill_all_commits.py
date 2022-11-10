"""backfill_all_commits

Revision ID: d3515ecea53d
Revises: 480dbbd48927
Create Date: 2022-11-09 11:33:51.081418

"""
import datetime
import uuid
from typing import List, Tuple

from alembic import op
from sqlalchemy import MetaData, Table, distinct, select

from conbench.entities.commit import Commit, GitHub, repository_to_name

# revision identifiers, used by Alembic.
revision = "d3515ecea53d"
down_revision = "480dbbd48927"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    commit_table: Table = meta.tables["commit"]
    github = GitHub()

    repos: List[Tuple[str]] = list(
        connection.execute(select(distinct(commit_table.c.repository)))
    )
    print(f"All repos: {repos}")

    for (repo,) in repos:
        if repo != repo.lower():
            print(f"{repo} has a (deprecated) uppercase letter; skipping")
            continue

        name = repository_to_name(repo)
        default_branch = github.get_default_branch(name)
        all_commits = github.get_commits_to_branch(
            name=name,
            branch=default_branch,
            since=datetime.datetime(1970, 1, 1),
            until=datetime.datetime.now(),
        )

        print(f"Checking if {len(all_commits)} commits are in the database")
        db_commits: List[Commit] = list(
            connection.execute(commit_table.select(commit_table.c.repository == repo))
        )
        db_commits_by_sha = {commit.sha: commit for commit in db_commits}
        print(f"Found {len(db_commits)} commits in the database")

        for commit_info in all_commits:
            sha = commit_info["sha"]
            if sha in db_commits_by_sha:
                # it's in the db; fill in branch/fork_point if they're missing
                db_commit = db_commits_by_sha[sha]
                if not db_commit.branch or not db_commit.fork_point_sha:
                    print(f"Adding default branch/fork_point_sha to sha {sha[:7]}")
                    connection.execute(
                        commit_table.update()
                        .where(commit_table.c.id == db_commit.id)
                        .values(branch=default_branch, fork_point_sha=sha)
                    )
                else:
                    print(f"sha {sha[:7]} was complete")

            else:
                # insert this commit into the db
                print(f"Inserting sha {sha[:7]} into the db")
                connection.execute(
                    commit_table.insert().values(
                        id=uuid.uuid4().hex,
                        sha=sha,
                        branch=default_branch,
                        fork_point_sha=sha,
                        repository=repo,
                        parent=commit_info["github"]["parent"],
                        timestamp=commit_info["github"]["date"],
                        message=commit_info["github"]["message"],
                        author_name=commit_info["github"]["author_name"],
                        author_login=commit_info["github"]["author_login"],
                        author_avatar=commit_info["github"]["author_avatar"],
                    )
                )


def downgrade():
    pass
