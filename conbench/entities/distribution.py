from sqlalchemy import func

from ..db import Session
from ..entities.commit import Commit


def get_commit_index(repository):
    ordered = (
        Session.query(Commit.id, Commit.sha, Commit.parent, Commit.timestamp)
        .filter(Commit.repository == repository)
        .order_by(Commit.timestamp.desc())
    ).cte("ordered_commits")
    return Session.query(ordered, func.row_number().over().label("row_number"))


def get_sha_row_number(repository, sha):
    index = get_commit_index(repository).subquery().alias("commit_index")
    return Session.query(index.c.row_number).filter(index.c.sha == sha)


def get_commits_up(repository, sha, limit):
    index = get_commit_index(repository).subquery().alias("commit_index")
    row_number = Session.query(index.c.row_number).filter(index.c.sha == sha)
    return Session.query(index).filter(index.c.row_number >= row_number).limit(limit)
