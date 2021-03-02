import copy

from ...api._examples import _api_machine_entity
from ...entities.summary import Summary
from ...tests.api import _asserts
from ...tests.api.test_benchmarks import VALID_PAYLOAD


def _expected_entity(machine):
    return _api_machine_entity(machine.id)


def create_benchmark_summary():
    data = copy.deepcopy(VALID_PAYLOAD)
    summary = Summary.create(data)
    return summary


class TestMachineGet(_asserts.GetEnforcer):
    url = "/api/machines/{}/"
    public = True

    def _create(self):
        summary = create_benchmark_summary()
        return summary.machine

    def test_get_machine(self, client):
        self.authenticate(client)
        machine = self._create()
        response = client.get(f"/api/machines/{machine.id}/")
        self.assert_200_ok(response, _expected_entity(machine))
