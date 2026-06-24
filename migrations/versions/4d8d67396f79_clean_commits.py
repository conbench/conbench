"""clean commits

We'd like to make the assumption that a Commit's sha == its fork_point_sha if and only
if it's on the default branch. Due to a few bugs, this wasn't always the case. We have
fixed those bugs, and now would like to clean up the historic commits so they follow
this rule.

Also, there was a short period of time where some servers had a bad GitHub PAT and
couldn't get rich commit info from GitHub. This script will add that info to those
commits.

Revision ID: 4d8d67396f79
Revises: d3515ecea53d
Create Date: 2022-12-15 11:08:12.526177

"""

import logging

from alembic import op
from sqlalchemy import MetaData, Table, distinct, select

from migrations.github import GitHubHTTPAPIClient, repository_to_name

# revision identifiers, used by Alembic.
revision = "4d8d67396f79"
down_revision = "d3515ecea53d"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)
log.setLevel("DEBUG")
_github = GitHubHTTPAPIClient()


def upgrade():
    connection = op.get_bind()
    meta = MetaData()
    meta.reflect(bind=connection)
    commit_table: Table = meta.tables["commit"]

    repos = list(connection.execute(select(distinct(commit_table.c.repository))))
    log.info(f"All repos: {repos}")

    for (repo,) in repos:
        if repo != repo.lower():
            log.info(f"{repo} has a (deprecated) uppercase letter; skipping")
            continue
        if repo == "":
            log.info("Repo is blank; skipping")
            continue

        name = repository_to_name(repo)
        default_branch = _github.get_default_branch(name)

        # ______ Enrich commits that are missing information, if possible ______

        log.info(
            f"Finding commits in repository {name} with missing enriched information"
        )
        commits = list(
            connection.execute(
                select(commit_table).where(
                    commit_table.c.repository == repo,
                    commit_table.c.timestamp.is_(None),
                    commit_table.c.sha != "",
                )
            )
        )
        log.info(f"Found {len(commits)} to fix")
        for commit in commits:
            commit_details = _github.get_commit(name, commit.sha)
            if not commit_details:
                log.error(f"Couldn't find commit details for sha '{commit.sha}'")
                commit_details = {}

            fork_point_sha = _github.get_fork_point_sha(name, commit.sha)
            if not fork_point_sha:
                log.error(f"Couldn't find the fork_point_sha for sha '{commit.sha}'")

            connection.execute(
                commit_table.update()
                .where(commit_table.c.id == commit.id)
                .values(
                    parent=commit_details.get("parent"),
                    timestamp=commit_details.get("date"),
                    message=commit_details.get("message") or "",
                    author_name=commit_details.get("author_name") or "",
                    author_login=commit_details.get("author_login"),
                    author_avatar=commit_details.get("author_avatar"),
                    fork_point_sha=fork_point_sha,
                )
            )

        # ______ (sha == fork_point_sha) --> (branch == default) ______

        log.info(
            f"Finding Commits in repository {name} where sha == fork_point_sha "
            f"but the branch is not '{default_branch}'",
        )
        commits = list(
            connection.execute(
                select(commit_table.c.id).where(
                    commit_table.c.repository == repo,
                    commit_table.c.sha == commit_table.c.fork_point_sha,
                    commit_table.c.branch != default_branch,
                )
            )
        )
        log.info(f"Found {len(commits)} to fix")
        for commit in commits:
            connection.execute(
                commit_table.update()
                .where(commit_table.c.id == commit.id)
                .values(branch=default_branch)
            )

        # ______ (sha != fork_point_sha) --> (branch != default) ______

        log.info(
            f"Finding Commits in repository {name} where sha != fork_point_sha "
            f"but the branch is '{default_branch}'",
        )
        commits = list(
            connection.execute(
                select(commit_table.c.id).where(
                    commit_table.c.repository == repo,
                    commit_table.c.sha != commit_table.c.fork_point_sha,
                    commit_table.c.branch == default_branch,
                )
            )
        )
        log.info(f"Found {len(commits)} to fix")
        for commit in commits:
            connection.execute(
                commit_table.update()
                .where(commit_table.c.id == commit.id)
                .values(branch=None)
            )


def downgrade():
    pass
