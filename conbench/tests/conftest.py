import pytest

from .. import create_application
from ..config import TestConfig
from ..db import Session, configure_engine, create_all, drop_all


pytest.register_assert_rewrite("conbench.tests.api._asserts")
pytest.register_assert_rewrite("conbench.tests.app._asserts")


@pytest.fixture(scope="session", autouse=True)
def create_db():
    configure_engine(TestConfig.SQLALCHEMY_DATABASE_URI)
    drop_all()
    create_all()


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
