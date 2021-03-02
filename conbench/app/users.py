import flask_login
import flask_wtf
import wtforms as w
import wtforms.validators as v

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..config import Config


class DeleteForm(flask_wtf.FlaskForm):
    delete = w.SubmitField("Delete")


class UserForm(flask_wtf.FlaskForm):
    email = w.StringField("Email", validators=[v.Email()])
    name = w.StringField("Name")
    submit = w.SubmitField("Submit")
    delete = w.SubmitField("Delete")


class CreateUserForm(flask_wtf.FlaskForm):
    name = w.StringField("Name", validators=[v.DataRequired()])
    email = w.StringField("Email", validators=[v.DataRequired(), v.Email()])
    password = w.PasswordField("Password", validators=[v.DataRequired()])
    submit = w.SubmitField("Submit")


class UserObject:
    def __init__(self, user):
        self.id = user["id"]
        self.name = user["name"]
        self.email = user["email"]


class User(AppEndpoint):
    form = UserForm

    def page(self, user, form):
        return self.render_template(
            "user-entity.html",
            application=Config.APPLICATION_NAME,
            title="User",
            user=user,
            form=form,
        )

    def get(self, user_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        user, response = self._get_user(user_id)
        if response.status_code != 200:
            self.flash("Error getting user.")
            return self.redirect("app.index")

        return self.page(user, self.form(obj=UserObject(user)))

    def post(self, user_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        form, response = self.form(), None
        delete_form, delete_response = DeleteForm(), None

        if form.delete.data:
            # delete button pressed
            if delete_form.validate_on_submit():
                delete_response = self.api_delete("api.user", user_id=user_id)
                if delete_response.status_code == 204:
                    self.flash("User deleted.")
                    return self.redirect("app.users")
        elif form.validate_on_submit():
            # submit button pressed
            response = self.api_put("api.user", form, user_id=user_id)
            if response.status_code == 200:
                self.flash("User updated.")
                return self.redirect("app.user", user_id=user_id)

        if response and not form.errors:
            self.flash(response.json["name"])
        if delete_response and not delete_form.errors:
            self.flash(delete_response.json["name"])

        csrf = {"csrf_token": ["The CSRF token is missing."]}
        if delete_form.errors == csrf:
            self.flash("The CSRF token is missing.")

        user, response = self._get_user(user_id)
        return self.page(user, form)

    def data(self, form):
        return {
            "name": form.name.data,
            "email": form.email.data,
        }

    def _get_user(self, user_id):
        response = self.api_get("api.user", user_id=user_id)
        return response.json, response


class UserList(AppEndpoint):
    def page(self, users):
        return self.render_template(
            "user-list.html",
            application=Config.APPLICATION_NAME,
            title="Users",
            users=users,
            delete_user_form=DeleteForm(),
        )

    def get(self):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        users, response = self._get_users()
        if response.status_code != 200:
            self.flash("Error getting users.")
            return self.redirect("app.index")

        return self.page(users)

    def _get_users(self):
        response = self.api_get("api.users")
        return response.json, response


class UserCreate(AppEndpoint):
    form = CreateUserForm

    def page(self, form):
        return self.render_template(
            "user-create.html",
            application=Config.APPLICATION_NAME,
            title="User Create",
            form=form,
        )

    def data(self, form):
        return {
            "name": form.name.data,
            "email": form.email.data,
            "password": form.password.data,
        }

    def get(self):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")
        return self.page(self.form())

    def post(self):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        form, response = self.form(), None
        if form.validate_on_submit():
            response = self.api_post("api.users", form)
            if response.status_code == 201:
                self.flash("User created.")
                return self.redirect("app.users")

        if response and not form.errors:
            self.flash(response.json["name"])

        return self.page(form)


rule(
    "/users/",
    view_func=UserList.as_view("users"),
    methods=["GET"],
)
rule(
    "/users/create/",
    view_func=UserCreate.as_view("user-create"),
    methods=["GET", "POST"],
)
rule(
    "/users/<user_id>/",
    view_func=User.as_view("user"),
    methods=["GET", "POST"],
)
