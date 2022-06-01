from ...api._examples import _api_commit_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(commit, parent=None):
    parent_commit_id = parent.id if parent else None
    return _api_commit_entity(commit.id, parent_commit_id)


def create_commit():
    _fixtures.benchmark_result(sha=_fixtures.PARENT)
    benchmark_result = _fixtures.benchmark_result()
    return benchmark_result.run.commit


class TestCommitGet(_asserts.GetEnforcer):
    url = "/api/commits/{}/"
    public = True

    def _create(self):
        return create_commit()

    def test_get_commit(self, client):
        self.authenticate(client)
        commit = self._create()
        response = client.get(f"/api/commits/{commit.id}/")
        parent = commit.get_parent_commit()
        self.assert_200_ok(response, _expected_entity(commit, parent))


class TestCommitList(_asserts.ListEnforcer):
    url = "/api/commits/"
    public = True

    def _create(self):
        return create_commit()

    def test_commit_list(self, client):
        self.authenticate(client)
        commit = self._create()
        response = client.get("/api/commits/")
        self.assert_200_ok(response, contains=_expected_entity(commit))

    def test_commit_list_filter_by_sha(self, client):
        sha = _fixtures.CHILD
        self.authenticate(client)
        commit = self._create()
        response = client.get(f"/api/commits/?commit={sha}")
        self.assert_200_ok(response, contains=_expected_entity(commit))

    def test_commit_list_filter_by_multiple_sha(self, client):
        sha1 = _fixtures.CHILD
        sha2 = _fixtures.PARENT
        self.authenticate(client)
        _fixtures.benchmark_result(sha=sha1)
        benchmark_result_1 = _fixtures.benchmark_result()
        _fixtures.benchmark_result(sha=sha2)
        benchmark_result_2 = _fixtures.benchmark_result()
        response = client.get(f"/api/commits/?commit={sha1},{sha2}")

        self.assert_200_ok(
            response, contains=_expected_entity(benchmark_result_1.run.commit)
        )
        self.assert_200_ok(
            response, contains=_expected_entity(benchmark_result_2.run.commit)
        )
