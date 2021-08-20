import tempfile

from conbench.util import Config, Connection, get_config

CONFIG = b"""
url: https://conbench.io
email: cole@example.com
password: woofwoof
host_name: machine100
"""


def test_get_config():
    with tempfile.NamedTemporaryFile(delete=False) as config_file:
        config_file.write(CONFIG)
        config_file.close()
        config = get_config(config_file.name)
        assert config == {
            "email": "cole@example.com",
            "password": "woofwoof",
            "url": "https://conbench.io",
            "host_name": "machine100",
        }


def test_default_config():
    config = Config({})
    assert config.login_url == "http://localhost:5000/api/login/"
    assert config.benchmarks_url == "http://localhost:5000/api/benchmarks/"
    credentials = {"email": "conbench@example.com", "password": "conbench"}
    assert config.credentials == credentials
    assert not config.host_name


def test_custom_config():
    custom = {
        "email": "cole@example.com",
        "password": "woofwoof",
        "url": "https://conbench.io",
        "host_name": "machine100",
    }
    config = Config(custom)
    assert config.login_url == "https://conbench.io/api/login/"
    assert config.benchmarks_url == "https://conbench.io/api/benchmarks/"
    credentials = {"email": "cole@example.com", "password": "woofwoof"}
    assert config.credentials == credentials
    assert config.host_name == "machine100"


EXPECTED_ERROR_JSON = """
POST https://url.example.com failed
{
  "message": "some error message",
  "code": "99"
}

"""

EXPECTED_ERROR_HTML = """
POST https://url.example.com failed
<html>ERROR!</html>

"""


def test_unexpected_response_json(capsys):
    class FakeResponse:
        pass

    url = "https://url.example.com"
    method = "POST"
    response = FakeResponse()
    response.content = '{"message": "some error message", "code": "99"}'

    connection = Connection()
    connection.session = "something not None"
    assert connection._unexpected_response(method, response, url) is None
    assert connection.session is None

    captured = capsys.readouterr()
    assert captured.out == EXPECTED_ERROR_JSON
    assert captured.err == ""


def test_unexpected_response_not_html(capsys):
    class FakeResponse:
        pass

    url = "https://url.example.com"
    method = "POST"
    response = FakeResponse()
    response.content = "<html>ERROR!</html>"

    connection = Connection()
    connection.session = "something not None"
    assert connection._unexpected_response(method, response, url) is None
    assert connection.session is None

    captured = capsys.readouterr()
    assert captured.out == EXPECTED_ERROR_HTML
    assert captured.err == ""
