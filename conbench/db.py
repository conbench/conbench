from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker


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
        connect_args={"options": "-c timezone=utc"},
    )
    session_maker.configure(bind=engine)


def create_all():
    from .entities._entity import Base

    Base.metadata.create_all(engine)
    engine.dispose()


def drop_all():
    from .entities._entity import Base

    print(Base.metadata.sorted_tables)
    print(reversed(Base.metadata.sorted_tables))
    for table in reversed(Base.metadata.sorted_tables):
        print(f"deleting {table}")
        table.drop(engine)
