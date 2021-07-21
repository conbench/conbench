from ...api._examples import _api_distribution_entity
from ...entities.distribution import Distribution
from ...tests.api import _asserts
from ...tests.api import _fixtures


def _expected_entity(distribution):
    return _api_distribution_entity(
        distribution.id,
        distribution.sha,
        distribution.case_id,
        distribution.context_id,
        distribution.machine_hash,
        distribution.observations,
    )


def create_distribution():
    summary = _fixtures.create_benchmark_summary()
    return Distribution.one(
        sha=summary.run.commit.sha,
        case_id=summary.case_id,
        context_id=summary.context_id,
        machine_hash=summary.run.machine.hash,
    )


class TestDistributionGet(_asserts.GetEnforcer):
    url = "/api/distributions/{}/"
    public = True

    def _create(self):
        return create_distribution()

    def test_get_distribution(self, client):
        self.authenticate(client)
        distribution = self._create()
        response = client.get(f"/api/distributions/{distribution.id}/")
        self.assert_200_ok(response, _expected_entity(distribution))


class TestDistributionList(_asserts.ListEnforcer):
    url = "/api/distributions/"
    public = True

    def _create(self):
        return create_distribution()

    def test_distribution_list(self, client):
        self.authenticate(client)
        distribution = self._create()
        response = client.get("/api/distributions/")
        self.assert_200_ok(response, contains=_expected_entity(distribution))
