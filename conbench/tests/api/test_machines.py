from ...api._examples import _api_machine_entity
from ...tests.api import _asserts
from ...tests.api import _fixtures


def _expected_entity(machine):
    return _api_machine_entity(machine.id)


class TestMachineGet(_asserts.GetEnforcer):
    url = "/api/machines/{}/"
    public = True

    def _create(self):
        summary = _fixtures.create_benchmark_summary()
        return summary.run.machine

    def test_get_machine(self, client):
        self.authenticate(client)
        machine = self._create()
        response = client.get(f"/api/machines/{machine.id}/")
        self.assert_200_ok(response, _expected_entity(machine))
