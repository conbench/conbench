import logging
import uuid

import flask as f
import flask_login
import marshmallow

from ..api import _google, rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint
from ..api.users import User

log = logging.getLogger(__name__)


class LoginSchema(marshmallow.Schema):
    email = marshmallow.fields.Email(required=True)
    password = marshmallow.fields.String(required=True)


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

        user = User.first(email=email)
        if user is None or not user.check_password(password):
            flask_login.logout_user()
            self.abort_400_bad_request("Invalid email or password.")

        flask_login.login_user(user, remember=True)
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


class GoogleAPI(ApiEndpoint):
    def get(self):
        """
        ---
        description: Google SSO.
        responses:
            "302": "302"
        tags:
          - Authentication
        """

        # Read query parameter `target`. Assume that the value is the URL that
        # the user actually wanted to visit before they were redirected to the
        # login page. `f.request.args` holds parsed URL query parameters.
        user_came_from_url = None
        if "target" in f.request.args:
            # Rely on Flask to do have done one level of URL-decoding
            user_came_from_url = f.request.args.get("target")
            log.info(f"api/google/, {user_came_from_url=}")

        return f.redirect(_google.gen_oidc_authz_req_url(user_came_from_url))


class CallbackAPI(ApiEndpoint):
    def get(self):
        """
        ---
        description: Google SSO callback.
        responses:
            "302": "302"
            "400": "400"
        tags:
          - Authentication
        """

        try:
            user_came_from_url, oidc_user = _google.conclude_oidc_flow()
        except Exception as e:
            self.abort_400_bad_request(
                f"OpenID Connect single sign-on flow failed: {e}."
            )

        email = oidc_user["email"]
        given = oidc_user.get("given_name", "")
        family = oidc_user.get("family_name", "")

        user = User.first(email=email)
        if user is None:
            data = {
                "email": email,
                "name": f"{given} {family}",
                "password": uuid.uuid4().hex,
            }
            user = User.create(data)
        flask_login.login_user(user)

        if len(user_came_from_url):
            return f.redirect(user_came_from_url)

        return self.redirect("app.index")


rule("/login/", view_func=LoginAPI.as_view("login"), methods=["POST"])
rule("/logout/", view_func=LogoutAPI.as_view("logout"), methods=["GET"])
rule("/google/", view_func=GoogleAPI.as_view("google"), methods=["GET"])
rule("/google/callback", view_func=CallbackAPI.as_view("callback"), methods=["GET"])

spec.components.schema("Login", schema=LoginSchema)
