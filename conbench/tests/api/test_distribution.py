from ...api._examples import _api_distribution_entity
from ...entities.distribution import Distribution
from ...tests.api import _asserts
from ...tests.api import _fixtures


def _expected_entity(distribution):
    return _api_distribution_entity(
        distribution.id,
        distribution.case_id,
        distribution.context_id,
    )


def get_distribution(summary):
    return Distribution.one(
        sha=summary.run.commit.sha,
        case_id=summary.case_id,
        context_id=summary.context_id,
        machine_hash=summary.run.machine.hash,
    )


class TestDistributionGet(_asserts.GetEnforcer):
    url = "/api/distribution/{}/"
    public = True

    def _create(self):
        return _fixtures.create_benchmark_summary()

    def test_get_distribution(self, client):
        self.authenticate(client)
        summary = self._create()
        distribution = get_distribution(summary)
        response = client.get(f"/api/distribution/{summary.id}/")
        self.assert_200_ok(response, contains=_expected_entity(distribution))
