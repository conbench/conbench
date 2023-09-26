import functools
import logging
import sys

import orjson
import psycopg2
import sqlalchemy.exc
import sqlalchemy.orm
import tenacity
from sqlalchemy import create_engine

from .config import Config

engine = None
session_maker = sqlalchemy.orm.sessionmaker()

# Module-global sqlalchemy session object, do not re-use in other modules.
# This is for DB interaction that happens outside of HTTP request processing
# context.
_session = sqlalchemy.orm.scoped_session(session_maker)


log = logging.getLogger(__name__)


log.info("psycopg2.__libpq_version__: %s", psycopg2.__libpq_version__)


# Pick less log verbosity when
logfunc = log.info
if "pytest" in sys.modules:
    logfunc = log.debug


def configure_engine(url):
    global engine, session_maker

    logfunc("create sqlalchemy DB engine")
    engine = create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        # As of today some requests take a (too) long while to generate a
        # response for. We want to improve that fundamentally over time. Until
        # then, it of course makes sense to deliver a response even if it takes
        # a while. Sometimes, the response generation duration is dominated by
        # a database query which takes a long time until it returns. We have
        # seen the libpq statement timeout to hit in every now and then when it
        # was set to 30 seconds. Setting it to 120 seconds increases the
        # likelihood to deliver an HTTP response at all. Increasing it beyond
        # 180 s probably does not make sense if we don't also increase timeout
        # constants for the HTTP reverse proxy(s) in front of Conbench. See
        # conbench/gunicorn-conf.py. Related tickets and discussions:
        # https://github.com/conbench/conbench/issues/599
        # https://github.com/conbench/conbench/pull/690
        # https://docs.sqlalchemy.org/en/20/core/engines.html#use-the-connect-args-dictionary-parameter
        connect_args={
            "options": "-c timezone=utc -c statement_timeout=120s",
            # The `connect_timeout` parameter is documented in
            # https://www.postgresql.org/docs/12/libpq-connect.html
            "connect_timeout": 3,  # unit: seconds
        },
        # This uses orjson for JSON-parsing JSONB fields from the database.
        # Anecdotal scenario seen with profiling: when loading 50000 result
        # objects from DB: psycopg2/_json.py:159 typecast_json took 2.5 s in
        # total (invoking stdblib JSONDecoder.decode 300000 times), with orjson
        # it took 0.3 s in total. No further noticeable gain with cysimdjson's
        # parser.
        json_deserializer=orjson.loads,  # pylint: disable=E1101
    )
    logfunc("bind engine to session")
    session_maker.configure(bind=engine)


# compute this only once.
@functools.cache
def get_tables_in_cleanup_order():
    # We need to remove rows from the many-to-many tables first to avoid
    # foreign key violations.

    from .entities._entity import Base as delarative_base

    tables = delarative_base.metadata.sorted_tables

    sort_by_name = ["benchmark_result"]

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
        _session.execute(table.delete())
        log.debug("deleted table: %s", table)

    _session.commit()
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
    stop=tenacity.stop_after_attempt(50),
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
    except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.ProgrammingError) as exc:
        # Seen in the wild:
        # sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateTable) relation "user" already exists
        if "already exists" in str(exc):
            log.info(
                "db.create_all(): ignore exception with 'already exists' in msg. "
                "Probably concurrent create_all() execution. Err: %s",
                str(exc),
            )
        else:
            raise

    logfunc("create_all(engine) returned. dispose()")
    engine.dispose()


def drop_all():
    from .entities._entity import Base

    _session.close()
    Base.metadata.drop_all(engine)
