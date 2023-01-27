import functools
import logging

import sqlalchemy.exc
import tenacity
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .config import Config

engine = None
session_maker = sessionmaker(future=True)
Session = scoped_session(session_maker)


log = logging.getLogger(__name__)


def configure_engine(url):
    global engine, session_maker, Session

    engine = create_engine(
        url,
        future=True,
        echo=False,
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=utc -c statement_timeout=30s"},
    )
    session_maker.configure(bind=engine)


# compute this only once.
@functools.cache
def get_tables_in_cleanup_order():
    # We need to remove rows from the many-to-many tables first to avoid
    # foreign key violations.

    from .entities._entity import Base as delarative_base

    tables = delarative_base.metadata.sorted_tables

    sort_by_name = ["benchmark_result", "run"]

    tabledict = {t.name: t for t in tables}
    sorted_tables = []
    for name in sort_by_name:
        # find table with that name, destructure `tabledict`. Assume that
        # `sort_by_name` only contains known table names.
        sorted_tables.append(tabledict.pop(name))

    unsorted_tables = list(tabledict.values())

    # Stich both lists together.
    return sorted_tables + unsorted_tables


def empty_db_tables():
    """
    For speeding up the test suite.

    Make sure that all tables are empty. A drop_all()/create_all() is a little
    slower than deleting individual table contents, especially when not using
    an in-memory database, as of the file system operations.
    """
    if not Config.TESTING:
        log.warning("empty_db_tables() called in non-testing mode, skip")
        return

    tables = get_tables_in_cleanup_order()

    for table in tables:
        Session.execute(table.delete())
        log.debug("deleted table: %s", table)

    Session.commit()
    log.debug("all deletions committed: %s", table)


def log_after_retry_attempt(retry_state: tenacity.RetryCallState):
    log.info(
        "result after attempt %s for %s: %s",
        retry_state.attempt_number,
        str(retry_state.fn),
        str(retry_state.outcome.exception()),  # type: ignore[union-attr]
    )


# `create_all()` below can fail with an `OperationalError` when the database
# isn't yet reachable. Can happen when web app and database are launched at
# about the same time (likely to happen only in dev environment). Apply a
# retrying strategy.
@tenacity.retry(
    retry=tenacity.retry_if_exception_type(sqlalchemy.exc.OperationalError),
    stop=tenacity.stop_after_attempt(10),
    wait=tenacity.wait_fixed(1),
    before=tenacity.before_log(log, logging.DEBUG),
    after=log_after_retry_attempt,
    reraise=True,
)
def create_all():
    from .entities._entity import Base

    # Gunicorn without --preload runs create_all() in potentially multiple
    # runners. That's fine, and only one of them can 'win' the DB creation
    # prize.
    try:
        Base.metadata.create_all(engine)
    except sqlalchemy.exc.IntegrityError as exc:
        if "already exists" in str(exc):
            log.info(
                "db.create_all(): ignore sqlalchemy.exc.IntegrityError. "
                "Probably concurrent create_all() execution. Err: %s",
                str(exc),
            )
        else:
            raise

    engine.dispose()


def drop_all():
    from .entities._entity import Base

    Session.close()
    Base.metadata.drop_all(engine)
