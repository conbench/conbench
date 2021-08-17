from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.commit import Commit, CommitSerializer


class CommitListAPI(ApiEndpoint):
    serializer = CommitSerializer()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of commits.
        responses:
            "200": "CommitList"
            "401": "401"
        tags:
          - Commits
        """
        commits = Commit.all(order_by=Commit.timestamp.desc(), limit=500)
        return self.serializer.many.dump(commits)


class CommitEntityAPI(ApiEndpoint):
    serializer = CommitSerializer()

    def _get(self, commit_id):
        try:
            commit = Commit.one(id=commit_id)
        except NotFound:
            self.abort_404_not_found()
        return commit

    @maybe_login_required
    def get(self, commit_id):
        """
        ---
        description: Get a commit.
        responses:
            "200": "CommitEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: commit_id
            in: path
            schema:
                type: string
        tags:
          - Commits
        """
        commit = self._get(commit_id)
        return self.serializer.one.dump(commit)


commit_entity_view = CommitEntityAPI.as_view("commit")
commit_list_view = CommitListAPI.as_view("commits")

rule(
    "/commits/<commit_id>/",
    view_func=commit_entity_view,
    methods=["GET"],
)
rule(
    "/commits/",
    view_func=commit_list_view,
    methods=["GET"],
)
