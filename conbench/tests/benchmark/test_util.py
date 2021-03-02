import tempfile

from conbench.util import Config, get_config


CONFIG = b"""
url: https://conbench.io
email: cole@example.com
password: woofwoof
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
        }


def test_default_config():
    config = Config({})
    assert config.login_url == "http://localhost:5000/api/login/"
    assert config.benchmarks_url == "http://localhost:5000/api/benchmarks/"
    credentials = {"email": "conbench@example.com", "password": "conbench"}
    assert config.credentials == credentials


def test_custom_config():
    custom = {
        "email": "cole@example.com",
        "password": "woofwoof",
        "url": "https://conbench.io",
    }
    config = Config(custom)
    assert config.login_url == "https://conbench.io/api/login/"
    assert config.benchmarks_url == "https://conbench.io/api/benchmarks/"
    credentials = {"email": "cole@example.com", "password": "woofwoof"}
    assert config.credentials == credentials
