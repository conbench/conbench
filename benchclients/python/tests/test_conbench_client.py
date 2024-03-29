import os

import pytest
from benchclients.conbench import ConbenchClientException
from benchclients.http import RetryingHTTPClientDeadlineReached
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug.wrappers import Response

from benchclients import ConbenchClient


def set_cb_base_url(h: HTTPServer):
    baseurl = h.url_for("/")
    os.environ["CONBENCH_URL"] = baseurl


def test_cc_init_and_base_url(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    assert c._base_url == httpserver.url_for("/").rstrip("/") + "/api"


@pytest.mark.parametrize("respjson", [[1, 2], {"1": "2"}])
def test_cc_get(httpserver: HTTPServer, respjson):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request("/api/foobar").respond_with_json(respjson)
    assert c.get("/foobar") == respjson


def test_cc_get_qparm(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request(
        "/api/bonjour", query_string={"whats": "up"}
    ).respond_with_json([2])
    assert c.get("/bonjour", params={"whats": "up"}) == [2]


def test_cc_get_all(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request(
        "/api/foobar", handler_type=HandlerType.ORDERED
    ).respond_with_json(
        {"data": [{"a": 1}, {"b": 2}], "metadata": {"next_page_cursor": "c"}}
    )
    httpserver.expect_request(
        "/api/foobar", query_string={"cursor": "c"}, handler_type=HandlerType.ORDERED
    ).respond_with_json({"data": [{"c": 3}], "metadata": {"next_page_cursor": None}})
    assert c.get_all("/foobar") == [{"a": 1}, {"b": 2}, {"c": 3}]


@pytest.mark.parametrize("respjson", [[1, 2], {"1": "2"}])
def test_cc_post(httpserver: HTTPServer, respjson):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_ordered_request(
        "/api/foobar", method="POST", json={"ql": "biz"}
    ).respond_with_json(respjson, status=201)
    assert c.post("/foobar", json={"ql": "biz"}) == respjson


@pytest.mark.parametrize("respjson", [[1, 2], {"1": "2"}])
def test_cc_put(httpserver: HTTPServer, respjson):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_ordered_request(
        "/api/foobar", method="PUT", json={"ql": "biz"}
    ).respond_with_json(respjson, status=201)
    assert c.put("/foobar", json={"ql": "biz"}) == respjson


def test_cc_post_expect_empty_body(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request(
        "/api/test", method="POST", json={"ql": "biz"}
    ).respond_with_data("", 201)
    assert c.post("/test", json={"ql": "biz"}) is None


def test_cc_put_expect_empty_body(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request(
        "/api/test", method="PUT", json={"ql": "biz"}
    ).respond_with_data("", 201)
    assert c.put("/test", json={"ql": "biz"}) is None


def test_cc_get_401(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()

    # This confirms that indeed one request was made, and that initiated the
    # machinery for triggering login. The login request is never sent.
    with pytest.raises(
        ConbenchClientException,
        match="credentials not set via parameters or the environment",
    ):
        httpserver.expect_request("/api/test").respond_with_data("", 401)
        c.get("/test")
        assert len(httpserver.log) == 1


def test_cc_performs_login_when_env_is_set(
    monkeypatch: pytest.MonkeyPatch, httpserver: HTTPServer
):
    set_cb_base_url(httpserver)
    monkeypatch.setenv("CONBENCH_EMAIL", "email")
    monkeypatch.setenv("CONBENCH_PASSWORD", "password")

    creds = {
        "email": os.getenv("CONBENCH_EMAIL"),
        "password": os.getenv("CONBENCH_PASSWORD"),
    }

    httpserver.expect_oneshot_request(
        "/api/login/", method="POST", json=creds
    ).respond_with_data("", status=204)

    # This confirms that the initialization of this object performs an HTTP
    # request.
    ConbenchClient(default_retry_for_seconds=15)

    # https://github.com/csernazs/pytest-httpserver/issues/35#issuecomment-1517903020
    assert len(httpserver.log) == 1


def test_cc_performs_login_from_kwargs(
    monkeypatch: pytest.MonkeyPatch, httpserver: HTTPServer
):
    url = httpserver.url_for("/")

    creds = {
        "email": os.getenv("CONBENCH_EMAIL"),
        "password": os.getenv("CONBENCH_PASSWORD"),
    }

    httpserver.expect_oneshot_request(
        "/api/login/", method="POST", json=creds
    ).respond_with_data("", status=204)

    # This confirms that the initialization of this object performs an HTTP
    # request.
    ConbenchClient(
        url=url,
        email=creds.get("email"),
        password=creds.get("password"),
        default_retry_for_seconds=15,
    )


def test_cc_get_500(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient(default_retry_for_seconds=15)
    # This test is expected to take ~15 seconds.
    httpserver.expect_request("/api/foobar").respond_with_response(Response(500))
    with pytest.raises(RetryingHTTPClientDeadlineReached, match="giving up after"):
        assert c.get("/foobar") == [1, 2]
