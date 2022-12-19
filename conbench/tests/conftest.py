import pytest

from .. import create_application
from ..config import TestConfig
from ..db import Session, configure_engine, create_all, drop_all, empty_db_tables

pytest.register_assert_rewrite("conbench.tests.api._asserts")
pytest.register_assert_rewrite("conbench.tests.app._asserts")


# Session-scope fixture, i.e. run this _once_ per test suite.
@pytest.fixture(scope="session")
def create_db_tables():
    configure_engine(TestConfig.SQLALCHEMY_DATABASE_URI)
    drop_all()
    create_all()


# Run this once per test, i.e. this can get expensive and contribute
# significantly to the duration of the test suite. `empty_db_tables()` is meant
# to be faster than drop_all()/create_all().
@pytest.fixture(autouse=True)
def clear_db_state_between_tests():
    empty_db_tables()


@pytest.fixture
def application():
    application = create_application(TestConfig)

    with application.app_context():
        pass

    yield application

    with application.app_context():
        Session.remove()


@pytest.fixture
def client(application):
    return application.test_client()


@pytest.fixture
def runner(application):
    return application.test_cli_runner()
