import pytest

from ...tests.app import _asserts


def assert_response_is_login_age(resp):
    assert resp.status_code == 200, (resp.status_code, resp.text)
    assert "<h4>Sign in</h4>" in resp.text, resp.text
    assert '<label for="password">Password</label>' in resp.text, resp.text


class TestCBenchmarks(_asserts.AppEndpointTest):
    url = "/c-benchmarks"

    @pytest.mark.parametrize(
        "relpath",
        ["/c-benchmarks", "/c-benchmarks/bname", "/c-benchmarks/bname/caseid"],
    )
    def test_access_control(self, client, monkeypatch, relpath):
        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
        self.logout(client)
        assert_response_is_login_age(client.get(relpath, follow_redirects=True))
