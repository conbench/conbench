import logging

import sqlalchemy.exc
import tenacity
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

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


def log_after_retry_attempt(retry_state: tenacity.RetryCallState):
    log.info(
        "result after attempt %s for %s: %s",
        retry_state.attempt_number,
        str(retry_state.fn),
        str(retry_state.outcome.exception()),
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

    Base.metadata.create_all(engine)
    engine.dispose()


def drop_all():
    from .entities._entity import Base

    Session.close()
    Base.metadata.drop_all(engine)
