from ..api import rule
from ..api._endpoint import ApiEndpoint
from ..entities._entity import NotFound
from ..entities.distribution import Distribution, DistributionSerializer


class DistributionListAPI(ApiEndpoint):
    serializer = DistributionSerializer()

    def get(self):
        """
        ---
        description: Get a list of distributions.
        responses:
            "200": "DistributionList"
            "401": "401"
        tags:
          - Distributions
        """
        distributions = Distribution.all(
            order_by=Distribution.last_timestamp.desc(), limit=500
        )
        return self.serializer.many.dump(distributions)


class DistributionEntityAPI(ApiEndpoint):
    serializer = DistributionSerializer()

    def _get(self, distribution_id):
        try:
            distribution = Distribution.one(id=distribution_id)
        except NotFound:
            self.abort_404_not_found()
        return distribution

    def get(self, distribution_id):
        """
        ---
        description: Get a distribution.
        responses:
            "200": "DistributionEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: distribution_id
            in: path
            schema:
                type: string
        tags:
          - Distributions
        """
        distribution = self._get(distribution_id)
        return self.serializer.one.dump(distribution)


distribution_entity_view = DistributionEntityAPI.as_view("distribution")
distribution_list_view = DistributionListAPI.as_view("distributions")

rule(
    "/distributions/<distribution_id>/",
    view_func=distribution_entity_view,
    methods=["GET"],
)
rule(
    "/distributions/",
    view_func=distribution_list_view,
    methods=["GET"],
)
