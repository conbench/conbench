from ...api._examples import _api_commit_entity
from ...tests.api import _asserts, _fixtures


def _expected_entity(commit, parent=None):
    parent_commit_id = parent.id if parent else None
    return _api_commit_entity(commit.id, parent_commit_id)


def create_commit():
    _fixtures.summary(sha=_fixtures.PARENT)
    summary = _fixtures.summary()
    return summary.run.commit


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
