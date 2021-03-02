import flask_login

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..config import Config


class Index(AppEndpoint):
    def page(self):
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
        )

    def get(self):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")
        return self.page()


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
