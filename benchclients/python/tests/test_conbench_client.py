import os

import pytest
import requests
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from benchclients import ConbenchClient


def set_cb_base_url(h: HTTPServer):
    baseurl = h.url_for("/")
    os.environ["CONBENCH_URL"] = baseurl


def test_cc_init_and_base_url(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    assert c.base_url == httpserver.url_for("/").rstrip("/") + "//api"


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


def test_cc_get_500(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request("/api/foobar").respond_with_response(Response(500))
    with pytest.raises(requests.exceptions.HTTPError, match="500 Server Error"):
        assert c.get("/foobar") == [1, 2]


@pytest.mark.parametrize("respjson", [[1, 2], {"1": "2"}])
def test_cc_post(httpserver: HTTPServer, respjson):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_ordered_request(
        "/api/foobar", method="POST", json={"ql": "biz"}
    ).respond_with_json(respjson)
    assert c.post("/foobar", json={"ql": "biz"}) == respjson


@pytest.mark.parametrize("respjson", [[1, 2], {"1": "2"}])
def test_cc_put(httpserver: HTTPServer, respjson):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_ordered_request(
        "/api/foobar", method="PUT", json={"ql": "biz"}
    ).respond_with_json(respjson)
    assert c.put("/foobar", json={"ql": "biz"}) == respjson


def test_cc_post_expect_empty_body(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request(
        "/api/test", method="POST", json={"ql": "biz"}
    ).respond_with_data("", 200)
    assert c.post("/test", json={"ql": "biz"}) is None


def test_cc_put_expect_empty_body(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    httpserver.expect_request(
        "/api/test", method="PUT", json={"ql": "biz"}
    ).respond_with_data("", 200)
    assert c.put("/test", json={"ql": "biz"}) is None


def test_cc_get_401(httpserver: HTTPServer):
    set_cb_base_url(httpserver)
    c = ConbenchClient()
    with pytest.raises(requests.exceptions.HTTPError, match="401 Client Error"):
        httpserver.expect_request("/api/test").respond_with_data("", 401)
        c.get("/test")
