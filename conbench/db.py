from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = None
session_maker = sessionmaker(future=True)
Session = scoped_session(session_maker)


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


def create_all():
    from .entities._entity import Base

    Base.metadata.create_all(engine)
    engine.dispose()


def drop_all():
    from .entities._entity import Base
    from .entities.data import Data
    from .entities.time import Time

    Session.close()
    Data.__table__.drop(engine)
    Time.__table__.drop(engine)
    Base.metadata.drop_all(engine)
