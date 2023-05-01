import copy
import re

from ...tests.api import _fixtures
from ...tests.app import _asserts


class TestRunGet(_asserts.GetEnforcer):
    url = "/runs/{}/"
    title = "Run"
    redirect_on_unknown = False

    def _create(self, client):
        self.create_benchmark(client)
        return _fixtures.VALID_RESULT_PAYLOAD["run_id"]

    def test_get_run_without_commit(self, client):
        self.authenticate(client)

        # Post a benchmark without a commit
        payload = copy.deepcopy(_fixtures.VALID_RESULT_PAYLOAD)
        del payload["github"]
        response = client.post("/api/benchmarks/", json=payload)
        assert response.status_code == 201

        # Ensure the run doesn't have a commit
        response = client.get(f'/api/runs/{payload["run_id"]}/')
        assert response.status_code == 200
        assert response.json["commit"] is None

        # Ensure the run page looks as expected
        self._assert_view(client, payload["run_id"])


class TestRunDelete(_asserts.DeleteEnforcer):
    def test_authenticated(self, client):
        self.create_benchmark(client)
        run_id = _fixtures.VALID_RESULT_PAYLOAD["run_id"]
        self.authenticate(client)
        response = client.get(f"/runs/{run_id}/")
        self.assert_page(response, "Run")
        assert f"{run_id}</li>".encode() in response.data

        data = {"delete": ["Delete"], "csrf_token": self.get_csrf_token(response)}
        response = client.post(f"/runs/{run_id}/", data=data, follow_redirects=True)
        self.assert_page(response, "Home")
        assert b"Run deleted." in response.data

        response = client.get(f"/runs/{run_id}/", follow_redirects=True)
        self.assert_page(response, "Run")
        assert re.search(r"Run ID unknown: \w+", response.text, flags=re.ASCII)

    def test_unauthenticated(self, client):
        self.create_benchmark(client)
        run_id = _fixtures.VALID_RESULT_PAYLOAD["run_id"]
        self.logout(client)
        data = {"delete": ["Delete"]}
        response = client.post(f"/runs/{run_id}/", data=data, follow_redirects=True)
        self.assert_login_page(response)

    def test_no_csrf_token(self, client):
        self.create_benchmark(client)
        run_id = _fixtures.VALID_RESULT_PAYLOAD["run_id"]
        self.authenticate(client)
        data = {"delete": ["Delete"]}
        response = client.post(f"/runs/{run_id}/", data=data, follow_redirects=True)
        self.assert_page(response, "Home")
        assert b"The CSRF token is missing." in response.data
