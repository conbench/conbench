from ...api._examples import _api_machine_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(machine):
    return _api_machine_entity(machine.id)


def create_machine():
    summary = _fixtures.summary()
    return summary.run.machine


class TestMachineGet(_asserts.GetEnforcer):
    url = "/api/machines/{}/"
    public = True

    def _create(self):
        return create_machine()

    def test_get_machine(self, client):
        self.authenticate(client)
        machine = self._create()
        response = client.get(f"/api/machines/{machine.id}/")
        self.assert_200_ok(response, _expected_entity(machine))


class TestMachineList(_asserts.ListEnforcer):
    url = "/api/machines/"
    public = True

    def _create(self):
        return create_machine()

    def test_machine_list(self, client):
        self.authenticate(client)
        machine = self._create()
        response = client.get("/api/machines/")
        self.assert_200_ok(response, contains=_expected_entity(machine))
