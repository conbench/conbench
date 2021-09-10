import flask_login

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.run import Run, RunSerializer
from ..entities.summary import Summary


class RunEntityAPI(ApiEndpoint):
    serializer = RunSerializer()

    def _get(self, run_id):
        try:
            run = Run.one(id=run_id)
        except NotFound:
            self.abort_404_not_found()
        return run

    @maybe_login_required
    def get(self, run_id):
        """
        ---
        description: Get a run.
        responses:
            "200": "RunEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: run_id
            in: path
            schema:
                type: string
        tags:
          - Runs
        """
        run = self._get(run_id)
        return self.serializer.one.dump(run)

    @flask_login.login_required
    def delete(self, run_id):
        """
        ---
        description: Delete a run.
        responses:
            "204": "204"
            "401": "401"
            "404": "404"
        parameters:
          - name: run_id
            in: path
            schema:
                type: string
        tags:
          - Runs
        """
        summaries = Summary.all(run_id=run_id)
        for summarie in summaries:
            summarie.delete()
        run = self._get(run_id)
        run.delete()
        return self.response_204_no_content()


class RunListAPI(ApiEndpoint):
    serializer = RunSerializer()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of runs.
        responses:
            "200": "RunList"
            "401": "401"
        tags:
          - Runs
        """
        runs = Run.all(order_by=Run.timestamp.desc(), limit=500)
        return self.serializer.many.dump(runs)


run_entity_view = RunEntityAPI.as_view("run")
run_list_view = RunListAPI.as_view("runs")

rule(
    "/runs/",
    view_func=run_list_view,
    methods=["GET"],
)
rule(
    "/runs/<run_id>/",
    view_func=run_entity_view,
    methods=["GET", "DELETE"],
)
