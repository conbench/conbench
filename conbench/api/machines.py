from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.machine import Machine, MachineSerializer


class MachineListAPI(ApiEndpoint):
    serializer = MachineSerializer()

    @maybe_login_required
    def get(self):
        """
        ---
        description: Get a list of machines.
        responses:
            "200": "MachineList"
            "401": "401"
        tags:
          - Machines
        """
        machines = Machine.all(order_by=Machine.name.asc(), limit=500)
        return self.serializer.many.dump(machines)


class MachineEntityAPI(ApiEndpoint):
    serializer = MachineSerializer()

    def _get(self, machine_id):
        try:
            machine = Machine.one(id=machine_id)
        except NotFound:
            self.abort_404_not_found()
        return machine

    @maybe_login_required
    def get(self, machine_id):
        """
        ---
        description: Get a machine.
        responses:
            "200": "MachineEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: machine_id
            in: path
            schema:
                type: string
        tags:
          - Machines
        """
        machine = self._get(machine_id)
        return self.serializer.one.dump(machine)


machine_entity_view = MachineEntityAPI.as_view("machine")
machine_list_view = MachineListAPI.as_view("machines")


rule(
    "/machines/<machine_id>/",
    view_func=machine_entity_view,
    methods=["GET"],
)
rule(
    "/machines/",
    view_func=machine_list_view,
    methods=["GET"],
)
