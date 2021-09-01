import re

from ...tests.api import _fixtures
from ...tests.helpers import _create_fixture_user, create_random_user


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
        assert b"<h1>Sign In</h1>" in r.data, r.data
        assert b"New user?" in r.data

    def assert_registration_page(self, r):
        self.assert_200_ok(r)
        assert b"<h1>Sign Up</h1>" in r.data, r.data
        assert b"Returning user?" in r.data

    def assert_index_page(self, r):
        self.assert_200_ok(r)
        assert b"Home - " in r.data, r.data

    def assert_page(self, r, title):
        self.assert_200_ok(r)
        title = "{} - ".format(title).encode()
        assert title in r.data, r.data

    def create_benchmark(self, client):
        self.authenticate(client)
        response = client.post("/api/benchmarks/", json=_fixtures.VALID_PAYLOAD)
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
        assert b"Sign In - Conbench" in response.data, response.data


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

        monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
        self.logout(client)
        response = client.get(entity_url, follow_redirects=True)
        assert new_id.encode() not in response.data
        assert b"Sign In - Conbench" in response.data, response.data

    def test_unknown(self, client):
        self.authenticate(client)
        unknown_url = self.url.format("unknown")
        response = client.get(unknown_url, follow_redirects=True)
        if getattr(self, "redirect_on_unknown", True):
            assert b"Home - Conbench" in response.data, response.data
        else:
            title = "{} - Conbench".format(self.title).encode()
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
