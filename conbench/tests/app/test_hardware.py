from ...tests.api import _fixtures
from ...tests.app import _asserts


class TestHardwares(_asserts.AppEndpointTest):
    def test_hardware_list_authenticated(self, client):
        self.create_benchmark(client)

        self.authenticate(client)
        response = client.get("/hardware/")
        self.assert_page(response, "Hardware")
        machine_name = _fixtures.VALID_PAYLOAD["machine_info"]["name"]
        assert f"<div>{machine_name}</div>".encode() in response.data

    def test_hardware_list_unauthenticated(self, client):
        response = client.get("/hardware/", follow_redirects=True)
        self.assert_login_page(response)


class TestHardware(_asserts.AppEndpointTest):
    def test_hardware_get_authenticated(self, client):
        self.create_benchmark(client)
        run_id = _fixtures.VALID_PAYLOAD["run_id"]
        response = client.get(f"/api/runs/{run_id}/")
        hardware_id = response.json["hardware"]["id"]

        self.authenticate(client)
        response = client.get(f"/hardware/{hardware_id}/")
        self.assert_page(response, "Hardware")
        assert "Hardware - Conbench".encode() in response.data

    def test_hardware_get_unauthenticated(self, client):
        self.create_benchmark(client)
        run_id = _fixtures.VALID_PAYLOAD["run_id"]
        response = client.get(f"/api/runs/{run_id}/")
        hardware_id = response.json["hardware"]["id"]

        response = client.get(f"/hardware/{hardware_id}/", follow_redirects=True)
        self.assert_login_page(response)

    def test_hardware_get_unknown(self, client):
        self.authenticate(client)
        response = client.get("/hardware/unknown/", follow_redirects=True)
        self.assert_index_page(response)
        assert b"Error getting hardware." in response.data
