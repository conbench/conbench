from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.hardware import Hardware, HardwareSerializer


class HardwareListAPI(ApiEndpoint):
    serializer = HardwareSerializer()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of hardware.
        responses:
            "200": "HardwareList"
            "401": "401"
        tags:
          - Hardware
        """
        hardware = Hardware.all(order_by=Hardware.name.asc(), limit=500)
        return self.serializer.many.dump(hardware)


class HardwareEntityAPI(ApiEndpoint):
    serializer = HardwareSerializer()

    def _get(self, hardware_id):
        try:
            hardware = Hardware.one(id=hardware_id)
        except NotFound:
            self.abort_404_not_found()
        return hardware

    @maybe_login_required
    def get(self, hardware_id):
        """
        ---
        description: Get a hardware.
        responses:
            "200": "HardwareEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: hardware_id
            in: path
            schema:
                type: string
        tags:
          - Hardware
        """
        hardware = self._get(hardware_id)
        return self.serializer.one.dump(hardware)


hardware_entity_view = HardwareEntityAPI.as_view("hardware")
hardware_list_view = HardwareListAPI.as_view("hardwares")


rule(
    "/hardware/<hardware_id>/",
    view_func=hardware_entity_view,
    methods=["GET"],
)
rule(
    "/hardware/",
    view_func=hardware_list_view,
    methods=["GET"],
)
