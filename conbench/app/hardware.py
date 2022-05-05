import flask as f
import flask_login

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..config import Config


class Hardware(AppEndpoint):
    def page(self, hardware):
        return self.render_template(
            "hardware-entity.html",
            application=Config.APPLICATION_NAME,
            title="Hardware",
            hardware=hardware,
        )

    def get(self, hardware_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        hardware, response = self._get_hardware(hardware_id)
        if response.status_code != 200:
            self.flash("Error getting hardware.")
            return self.redirect("app.index")

        return self.page(hardware)

    def _get_hardware(self, hardware_id):
        response = self.api_get("api.hardware", hardware_id=hardware_id)
        return response.json, response


class HardwareList(AppEndpoint):
    def page(self, hardwares):
        return self.render_template(
            "hardware-list.html",
            application=Config.APPLICATION_NAME,
            title="Hardware",
            hardwares=hardwares,
            search_value=f.request.args.get("search"),
        )

    def get(self):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        hardwares, response = self._get_hardwares()
        if response.status_code != 200:
            self.flash("Error getting hardwares.")
            return self.redirect("app.index")

        return self.page(hardwares)

    def _get_hardwares(self):
        response = self.api_get("api.hardwares")
        return response.json, response


rule(
    "/hardware/",
    view_func=HardwareList.as_view("hardwares"),
    methods=["GET"],
)
rule(
    "/hardware/<hardware_id>/",
    view_func=Hardware.as_view("hardware"),
    methods=["GET"],
)
