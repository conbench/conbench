from ...api._examples import _api_hardware_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(hardware):
    return _api_hardware_entity(hardware.id, hardware.name, hardware.type)


def create_hardware(hardware_type="machine"):
    summary = _fixtures.summary(hardware_type=hardware_type)
    return summary.run.hardware


class TestHardwareGet(_asserts.GetEnforcer):
    url = "/api/hardware/{}/"
    public = True

    def _create(self):
        return create_hardware()

    def test_get_machine(self, client):
        self.authenticate(client)
        machine = create_hardware(hardware_type="machine")
        response = client.get(f"/api/hardware/{machine.id}/")
        self.assert_200_ok(response, _expected_entity(machine))

    def test_get_cluster(self, client):
        self.authenticate(client)
        cluster = create_hardware(hardware_type="cluster")
        response = client.get(f"/api/hardware/{cluster.id}/")
        self.assert_200_ok(response, _expected_entity(cluster))


class TestHardwareList(_asserts.ListEnforcer):
    url = "/api/hardware/"
    public = True

    def _create(self):
        return create_hardware()

    def test_machine_list(self, client):
        self.authenticate(client)
        machine = create_hardware(hardware_type="machine")
        cluster = create_hardware(hardware_type="cluster")
        response = client.get("/api/hardware/")
        self.assert_200_ok(response, contains=_expected_entity(machine))
        self.assert_200_ok(response, contains=_expected_entity(cluster))
