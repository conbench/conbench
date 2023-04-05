import logging
import re
import urllib.parse

from ...tests.api import _fixtures
from ...tests.helpers import _create_fixture_user, create_random_user

log = logging.getLogger(__name__)


class AppEndpointTest:
    def authenticate(self, client):
        self._create_fixture_user()
        self.login(client, "fixture@example.com", "fixture")

    def login(self, client, email, password):
        response = client.get("/login/")
        csrf_token = self.get_csrf_token(response)
        return client.post(
            "/login/",
            data=dict(email=email, password=password, csrf_token=csrf_token),
            follow_redirects=True,
        )

    def logout(self, client):
        client.get("/logout/")

    def get_csrf_token(self, response):
        field = b'<input id="csrf_token" name="csrf_token" type="hidden" value="(.*)">'
        csrf_token = (
            re.search(
                field,
                response.data,
            )
            .group(1)
            .decode("utf-8")
        )
        return csrf_token

    def create_random_user(self):
        return create_random_user()

    def _create_fixture_user(self):
        return _create_fixture_user()

    def assert_200_ok(self, r):
        assert r.status_code == 200, r.status_code
        assert r.content_type == "text/html; charset=utf-8", r.content_type

    def assert_404_not_found(self, r):
        assert r.status_code == 404, r.status_code
        # TODO: How to make this an HTML error page?
        # While still having json error rs for the API.
        assert r.content_type == "application/json", r.content_type
        assert r.json == {"code": 404, "name": "Not Found"}, r.json

    def assert_login_page(self, r):
        self.assert_200_ok(r)
        assert b"Sign in" in r.data
        assert b"New user?" in r.data

    def assert_registration_page(self, r):
        self.assert_200_ok(r)
        assert b"<h1>Sign Up</h1>" in r.data, r.data
        assert b"Returning user?" in r.data

    def assert_index_page(self, r):
        self.assert_200_ok(r)
        assert b"local-dev-conbench" in r.data
        assert b'<html lang="en">' in r.data
        # assert b"Login" in r.data

    def assert_page(self, r, title):
        self.assert_200_ok(r)
        # The HTML <title> tag starts with the conbench deployment name, in
        # this case `local-dev-conbench` and then contains a " - " seperator,
        # followed by the more specific page name
        assert b"local-dev-conbench - " in r.data

    def create_benchmark(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=_fixtures.VALID_PAYLOAD)
        assert response.status_code == 201, response.text
        benchmark_id = response.json["id"]
        self.logout(client)
        return benchmark_id


class Enforcer(AppEndpointTest):
    def test_authenticated(self, client):
        raise NotImplementedError()

    def test_unauthenticated(self, client):
        raise NotImplementedError()

    def test_public_data_off(self, client, monkeypatch):
        raise NotImplementedError()


class ListEnforcer(Enforcer):
    def _assert_view(self, client, new_id):
        response = client.get(self.url)
        self.assert_page(response, self.title)
        assert f"{new_id}".encode() in response.data

    def test_authenticated(self, client, monkeypatch):
        new_id = self._create(client)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "on")
        self.authenticate(client)
        self._assert_view(client, new_id)

    def test_unauthenticated(self, client, monkeypatch):
        new_id = self._create(client)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "on")
        self.logout(client)
        self._assert_view(client, new_id)

    def test_public_data_off(self, client, monkeypatch):
        new_id = self._create(client)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
        self.logout(client)
        response = client.get(self.url, follow_redirects=True)
        assert new_id.encode() not in response.data
        assert b"Sign In" in response.data, response.data


class GetEnforcer(Enforcer):
    def _assert_view(self, client, new_id):
        response = client.get(self.url.format(new_id))
        self.assert_page(response, self.title)
        assert f'{new_id.split("...")[0]}'.encode() in response.data

    def test_authenticated(self, client, monkeypatch):
        new_id = self._create(client)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "on")
        self.authenticate(client)
        self._assert_view(client, new_id)

    def test_unauthenticated(self, client, monkeypatch):
        new_id = self._create(client)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "on")
        self.logout(client)
        self._assert_view(client, new_id)

    def test_public_data_off(self, client, monkeypatch):
        new_id = self._create(client)
        entity_url = self.url.format(new_id)

        # expect this to be a relative url with a trailing slash, example:
        # /batches/7b2fdd9f929d47b9960152090d47f8e6/
        log.debug("entity url: %s", entity_url)

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
        self.logout(client)

        r = client.get(entity_url, follow_redirects=False)

        # Confirm this to be a redirect response.
        assert r.status_code == 302, f"unexpected resp: {r.text}"

        # Inspect the URL that we redirect the user agent to.
        loc_url = r.headers.get("location")
        log.debug("response Location header: %s", loc_url)
        res = urllib.parse.urlparse(loc_url)
        log.debug("loc url components: %s", res)

        # Confirm that there is a query part, and that it roughly looks like
        # desired.
        assert res.query.startswith("target=")

        # Now inspect the exact structure of the URL query string.
        qargs = res = urllib.parse.parse_qs(res.query)
        log.info("loc url query decoded: %s", qargs)
        assert "target" in qargs
        assert len(qargs["target"]) == 1
        target_url = qargs["target"][0]
        assert target_url.startswith(entity_url)

        # A bit of tuning was required to get here, see
        # https://github.com/conbench/conbench/issues/525
        assert target_url == entity_url

        # There might be more redirects here, e.g. from / to /login/
        r2 = client.get(r.headers.get("location"), follow_redirects=True)

        # Note(JP): I have disabled this assertion. It was confirming that the
        # entitity ID (as in for example
        # /batches/7b2fdd9f929d47b9960152090d47f8e6) would not appear in the
        # response body in the final response after all redirects after access
        # control. This started to fail with enabled SSO because this ID is
        # then part of the non-sensitive target URL and therefore appears in
        # the `href` of the button/link for SSO flow initiation. If the goal of
        # this assertion was to make sure that no entity details _other than_
        # the entity ID end up showing up on the login page, then this needs to
        # be reworked.
        # assert new_id.encode() not in r2.data

        assert b"local-dev-conbench - Sign In" in r2.data, r2.data

    def test_unknown(self, client):
        self.authenticate(client)
        unknown_url = self.url.format("unknown")

        response = client.get(unknown_url, follow_redirects=True)

        # Special case for the compare API where the parameter
        # is part of the URL path (not query parameter) and needs to
        # match a certain pattern. We can make this nicer via UI later,
        # but for starters a non-matching URL pattern is OK / nice to be
        # treated as 404 not found (with a hint for the user).
        if "compare" in unknown_url and response.status_code == 404:
            if "not found: ellipsis (...) expected as part of URL":
                return

        if getattr(self, "redirect_on_unknown", True):
            assert b"local-dev-conbench - Home" in response.data, response.data
        else:
            title = f"local-dev-conbench - {self.title}".encode()
            assert title in response.data, response.data


class CreateEnforcer(Enforcer):
    def test_authenticated(self, client):
        raise NotImplementedError()

    def test_unauthenticated(self, client):
        raise NotImplementedError()

    def test_no_csrf_token(self, client):
        raise NotImplementedError()


class DeleteEnforcer(Enforcer):
    def test_authenticated(self, client):
        raise NotImplementedError()

    def test_unauthenticated(self, client):
        raise NotImplementedError()

    def test_no_csrf_token(self, client):
        raise NotImplementedError()

    def test_public_data_off(self, client, monkeypatch):
        pass
