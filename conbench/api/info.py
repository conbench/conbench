from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.info import Info, InfoSerializer


class InfoListAPI(ApiEndpoint):
    serializer = InfoSerializer()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of benchmark info.
        responses:
            "200": "InfoList"
            "401": "401"
        tags:
          - Info
        """
        info = Info.all(order_by=Info.id.asc(), limit=500)
        return self.serializer.many.dump(info)


class InfoEntityAPI(ApiEndpoint):
    serializer = InfoSerializer()

    def _get(self, info_id):
        try:
            info = Info.one(id=info_id)
        except NotFound:
            self.abort_404_not_found()
        return info

    @maybe_login_required
    def get(self, info_id):
        """
        ---
        description: Get benchmark info.
        responses:
            "200": "InfoEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: info_id
            in: path
            schema:
                type: string
        tags:
          - Info
        """
        info = self._get(info_id)
        return self.serializer.one.dump(info)


info_entity_view = InfoEntityAPI.as_view("info")
info_list_view = InfoListAPI.as_view("infos")

rule(
    "/info/<info_id>/",
    view_func=info_entity_view,
    methods=["GET"],
)
rule(
    "/info/",
    view_func=info_list_view,
    methods=["GET"],
)
