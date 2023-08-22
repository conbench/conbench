import flask
import pytest


@pytest.fixture
def runner():
    return flask.Flask("test").test_cli_runner()
