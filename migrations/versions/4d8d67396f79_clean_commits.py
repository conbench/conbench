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
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "4d8d67396f79"
down_revision = "d3515ecea53d"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)
log.setLevel("DEBUG")


def upgrade():
    # Before importing conbench.entities, monkeypatch the conbench.entities Session
    # to use the alembic Session
    alembic_session = Session(op.get_bind())
    from conbench.entities import _entity

    _entity.Session = alembic_session
    from conbench.entities.commit import Commit, GitHub, repository_to_name

    github = GitHub()

    repos = alembic_session.query(Commit.repository).distinct().all()
    log.info(f"All repos: {repos}")

    for (repo,) in repos:
        if repo != repo.lower():
            log.info(f"{repo} has a (deprecated) uppercase letter; skipping")
            continue
        if repo == "":
            log.info("Repo is blank; skipping")
            continue

        name = repository_to_name(repo)
        default_branch = github.get_default_branch(name)

        # ______ Enrich commits that are missing information, if possible ______

        log.info(
            f"Finding commits in repository {name} with missing enriched information"
        )
        commits = Commit.all(
            repository=repo, filter_args=[Commit.timestamp.is_(None), Commit.sha != ""]
        )
        log.info(f"Found {len(commits)} to fix")
        for commit in commits:
            commit_details = github.get_commit(name, commit.sha)
            if not commit_details:
                log.error(f"Couldn't find commit details for sha '{commit.sha}'")
                commit_details = {}

            fork_point_sha = github.get_fork_point_sha(name, commit.sha)
            if not fork_point_sha:
                log.error(f"Couldn't find the fork_point_sha for sha '{commit.sha}'")

            commit.update(
                {
                    "parent": commit_details.get("parent"),
                    "timestamp": commit_details.get("date"),
                    "message": commit_details.get("message") or "",
                    "author_name": commit_details.get("author_name") or "",
                    "author_login": commit_details.get("author_login"),
                    "author_avatar": commit_details.get("author_avatar"),
                    "fork_point_sha": fork_point_sha,
                }
            )

        # ______ (sha == fork_point_sha) --> (branch == default) ______

        log.info(
            f"Finding Commits in repository {name} where sha == fork_point_sha "
            f"but the branch is not '{default_branch}'",
        )
        commits = Commit.all(
            repository=repo,
            filter_args=[
                Commit.sha == Commit.fork_point_sha,
                Commit.branch != default_branch,
            ],
        )
        log.info(f"Found {len(commits)} to fix")
        for commit in commits:
            commit.update({"branch": default_branch})

        # ______ (sha != fork_point_sha) --> (branch != default) ______

        log.info(
            f"Finding Commits in repository {name} where sha != fork_point_sha "
            f"but the branch is '{default_branch}'",
        )
        commits = Commit.all(
            repository=repo,
            filter_args=[
                Commit.sha != Commit.fork_point_sha,
                Commit.branch == default_branch,
            ],
        )
        log.info(f"Found {len(commits)} to fix")
        for commit in commits:
            commit.update({"branch": None})


def downgrade():
    pass
