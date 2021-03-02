import flask_login
import marshmallow


from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint
from ..api.users import User


class LoginSchema(marshmallow.Schema):
    email = marshmallow.fields.Email(required=True)
    password = marshmallow.fields.String(required=True)
    remember_me = marshmallow.fields.Boolean(default=False)


class LoginAPI(ApiEndpoint):
    schema = LoginSchema()

    def post(self):
        """
        ---
        description: Login with email and password.
        responses:
            "204": "204"
            "400": "400"
        requestBody:
            content:
                application/json:
                    schema: Login
        tags:
          - Authentication
        """

        data = self.validate(self.schema)
        email = data.get("email")
        password = data.get("password")
        remember_me = data.get("remember_me")

        user = User.first(email=email)
        if user is None or not user.check_password(password):
            flask_login.logout_user()
            self.abort_400_bad_request("Invalid email or password.")

        flask_login.login_user(user, remember=remember_me)
        return self.response_204_no_content()


class LogoutAPI(ApiEndpoint):
    def get(self):
        """
        ---
        description: Logout.
        responses:
            "204": "204"
        tags:
          - Authentication
        """
        flask_login.logout_user()
        return self.response_204_no_content()


rule("/login/", view_func=LoginAPI.as_view("login"), methods=["POST"])
rule("/logout/", view_func=LogoutAPI.as_view("logout"), methods=["GET"])
spec.components.schema("Login", schema=LoginSchema)
