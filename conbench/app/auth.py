import os

import flask_login
import flask_wtf
import wtforms as w
import wtforms.validators as v

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..config import Config
from ..entities.user import User


class Logout(AppEndpoint):
    def get(self):
        flask_login.logout_user()
        return self.redirect("app.index")


class LoginForm(flask_wtf.FlaskForm):
    email = w.StringField("Email", validators=[v.DataRequired()])
    password = w.PasswordField("Password", validators=[v.DataRequired()])
    remember_me = w.BooleanField("Remember Me")
    submit = w.SubmitField("Submit")


class Login(AppEndpoint):
    form = LoginForm

    def page(self, form):
        sso = os.environ.get("GOOGLE_CLIENT_ID", None) is not None
        return self.render_template(
            "login.html",
            application=Config.APPLICATION_NAME,
            title="Sign In",
            form=form,
            sso=sso,
        )

    def data(self, form):
        return {
            "email": form.email.data,
            "password": form.password.data,
            "remember_me": form.remember_me.data,
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
            response = self.api_post("api.login", form)
            if response.status_code == 204:
                # TODO: remove this last query from frontend
                user = User.first(email=form.email.data)
                flask_login.login_user(user, remember=form.remember_me.data)
                return self.redirect("app.index")
            else:
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
