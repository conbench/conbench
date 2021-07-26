from ..api import rule
from ..api._endpoint import ApiEndpoint
from ..entities._entity import NotFound
from ..entities.distribution import get_distribution_history, DistributionSerializer
from ..entities.summary import Summary


class DistributionEntityAPI(ApiEndpoint):
    serializer = DistributionSerializer()

    def _get(self, benchmark_id):
        try:
            summary = Summary.one(id=benchmark_id)
        except NotFound:
            self.abort_404_not_found()
        return get_distribution_history(
            summary.run.commit.repository,
            summary.run.commit.sha,
            summary.case_id,
            summary.context_id,
            summary.run.machine.hash,
        )

    def get(self, benchmark_id):
        """
        ---
        description: Get benchmark distribution history.
        responses:
            "200": "DistributionList"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_id
            in: path
            schema:
                type: string
        tags:
          - Distribution
        """
        distribution = self._get(benchmark_id)
        return self.serializer.many.dump(distribution)


distribution_entity_view = DistributionEntityAPI.as_view("distribution")

rule(
    "/distribution/<benchmark_id>/",
    view_func=distribution_entity_view,
    methods=["GET"],
)
