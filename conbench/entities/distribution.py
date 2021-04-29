from sqlalchemy import func

from ..db import Session
from ..entities.commit import Commit
from ..entities.run import Run
from ..entities.summary import Summary


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


def get_distribution(repository, sha, limit):
    commits_up = get_commits_up(repository, sha, limit).subquery().alias("commits_up")
    return (
        Session.query(
            Summary.case_id,
            Summary.context_id,
            Summary.machine_id,
            func.max(Summary.unit).label("unit"),
            func.avg(Summary.mean).label("mean_mean"),
            func.stddev(Summary.mean).label("mean_sd"),
            func.avg(Summary.min).label("min_mean"),
            func.stddev(Summary.min).label("min_sd"),
            func.avg(Summary.max).label("max_mean"),
            func.stddev(Summary.max).label("max_sd"),
            func.avg(Summary.median).label("median_mean"),
            func.stddev(Summary.median).label("median_sd"),
            func.min(commits_up.c.timestamp).label("first_timestamp"),
            func.max(commits_up.c.timestamp).label("last_timestamp"),
            func.count(Summary.mean).label("n_observations_used"),
        )
        .group_by(Summary.case_id, Summary.context_id, Summary.machine_id)
        .join(Run, Run.id == Summary.run_id)
        .join(commits_up, commits_up.c.id == Run.commit_id)
    )
