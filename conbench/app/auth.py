import logging
import os
from typing import Optional

import flask as f
import flask_login
import flask_wtf
import wtforms as w
import wtforms.validators as v

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..config import Config
from ..entities.user import User

log = logging.getLogger(__name__)


class Logout(AppEndpoint):
    def get(self):
        flask_login.logout_user()
        return self.redirect("app.index")


class LoginForm(flask_wtf.FlaskForm):
    email = w.StringField("Email", validators=[v.DataRequired()])
    password = w.PasswordField("Password", validators=[v.DataRequired()])
    submit = w.SubmitField("Submit")


class Login(AppEndpoint):
    form = LoginForm

    def page(self, form, target_url_after_login: Optional[str] = None):
        """
        `target_url_after_login` is meant to carry an absolute or relative URL,
        the target to redirect the user to after login was successful.
        """

        show_sso_button = False

        if (
            Config.OIDC_CLIENT_ID
            and Config.OIDC_CLIENT_SECRET
            and Config.OIDC_ISSUER_URL
        ):
            show_sso_button = True

        # Legacy method for determining whether or not to show the SSO
        # link/button: remove when GOOGLE_CLIENT_ID gets phased out.
        if os.environ.get("GOOGLE_CLIENT_ID") is not None:
            show_sso_button = True

        return self.render_template(
            "login.html",
            application=Config.APPLICATION_NAME,
            title="Sign In",
            form=form,
            sso=show_sso_button,
            # If `target_url_after_login` is Falsy (e.g. emtpy string) then
            # expect template to not add a query parameter to the login link.
            target_url_after_login=target_url_after_login,
        )

    def data(self, form):
        return {
            "email": form.email.data,
            "password": form.password.data,
        }

    def get(self):
        # Read query parameter `target`. Assume that the value is the URL that
        # the user actually wanted to visit before they were redirected to the
        # login page. `f.request.args` holds parsed (i.e. URL-decoded) URL
        # query parameters.
        user_came_from_url = ""
        if "target" in f.request.args:
            user_came_from_url = f.request.args.get("target")
            log.debug("render login page. target param: %s", user_came_from_url)

        if flask_login.current_user.is_authenticated:
            # Redirect to target if set? Might create infinite redirect loop.
            return self.redirect("app.index")

        return self.page(self.form(), target_url_after_login=user_came_from_url)

    def post(self):
        """
        Note: redirect-to-target-after-login not yet implemented
        """
        if flask_login.current_user.is_authenticated:
            return self.redirect("app.index")

        form = self.form()

        if form.validate_on_submit():
            response = self.api_post("api.login", form)

            if response.status_code == 204:
                # TODO: remove this last query from frontend
                user = User.first(email=form.email.data)
                # NOTE(JP): this is the second time that we call
                # `flask_login.login_user` while the actual user agent waits
                # for an HTTP response.
                flask_login.login_user(user)

                return self.redirect("app.index")
            else:
                log.info(
                    "login request failed, response details: %s, %s",
                    response,
                    response.text,
                )
                self.flash("Invalid email or password.", "danger")

        return self.page(form)


class RegistrationForm(flask_wtf.FlaskForm):
    name = w.StringField("Name", validators=[v.DataRequired()])
    email = w.StringField("Email", validators=[v.DataRequired(), v.Email()])
    password = w.PasswordField("Password", validators=[v.DataRequired()])
    password2 = w.PasswordField(
        "Confirm Password", validators=[v.DataRequired(), v.EqualTo("password")]
    )
    secret = w.StringField("Registration Key", validators=[v.DataRequired()])
    submit = w.SubmitField("Submit")


class Register(AppEndpoint):
    form = RegistrationForm

    def page(self, form):
        return self.render_template(
            "register.html",
            application=Config.APPLICATION_NAME,
            title="Sign Up",
            form=form,
        )

    def data(self, form):
        return {
            "name": form.name.data,
            "email": form.email.data,
            "password": form.password.data,
            "secret": form.secret.data,
        }

    def get(self):
        if flask_login.current_user.is_authenticated:
            return self.redirect("app.index")
        return self.page(self.form())

    def post(self):
        if flask_login.current_user.is_authenticated:
            return self.redirect("app.index")

        form = self.form()
        if form.validate_on_submit():
            response = self.api_post("api.register", form)
            if response.status_code == 201:
                self.flash("Welcome! Please login.", "success")
                return self.redirect("app.login")
            else:
                self.flash("Registration failed.", "danger")

        return self.page(form)


rule("/register/", view_func=Register.as_view("register"), methods=["GET", "POST"])
rule("/login/", view_func=Login.as_view("login"), methods=["GET", "POST"])
rule("/logout/", view_func=Logout.as_view("logout"), methods=["GET"])
