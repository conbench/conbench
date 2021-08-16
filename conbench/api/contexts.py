from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.context import Context, ContextSerializer


class ContextListAPI(ApiEndpoint):
    serializer = ContextSerializer()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of contexts.
        responses:
            "200": "ContextList"
            "401": "401"
        tags:
          - Contexts
        """
        contexts = Context.all(order_by=Context.id.asc(), limit=500)
        return self.serializer.many.dump(contexts)


class ContextEntityAPI(ApiEndpoint):
    serializer = ContextSerializer()

    def _get(self, context_id):
        try:
            context = Context.one(id=context_id)
        except NotFound:
            self.abort_404_not_found()
        return context

    @maybe_login_required
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
context_list_view = ContextListAPI.as_view("contexts")

rule(
    "/contexts/<context_id>/",
    view_func=context_entity_view,
    methods=["GET"],
)
rule(
    "/contexts/",
    view_func=context_list_view,
    methods=["GET"],
)
