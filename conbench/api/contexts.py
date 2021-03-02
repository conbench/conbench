from ..api import rule
from ..api._endpoint import ApiEndpoint
from ..entities._entity import NotFound
from ..entities.context import Context, ContextSerializer


class ContextEntityAPI(ApiEndpoint):
    serializer = ContextSerializer()

    def _get(self, context_id):
        try:
            context = Context.one(id=context_id)
        except NotFound:
            self.abort_404_not_found()
        return context

    def get(self, context_id):
        """
        ---
        description: Get a context.
        responses:
            "200": "ContextEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: context_id
            in: path
            schema:
                type: string
        tags:
          - Contexts
        """
        context = self._get(context_id)
        return self.serializer.one.dump(context)


context_entity_view = ContextEntityAPI.as_view("context")

rule(
    "/contexts/<context_id>/",
    view_func=context_entity_view,
    methods=["GET"],
)
