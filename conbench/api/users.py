import flask_login
import marshmallow

from ..api import rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint
from ..config import Config
from ..entities._entity import NotFound
from ..entities.user import User, UserSchema, UserSerializer


class UserValidationMixin:
    def validate_user(self, schema, user=None):
        data = self.validate(schema)
        email = data.get("email")

        # user update case (no change to email)
        if user and user.email == email:
            return data

        other = User.first(email=email)
        if other:
            message = "Email address already in use."
            self.abort_400_bad_request({"email": [message]})

        return data


class UserEntityAPI(ApiEndpoint, UserValidationMixin):
    serializer = UserSerializer()
    schema = UserSchema()

    def _get(self, user_id):
        try:
            user = User.one(id=user_id)
        except NotFound:
            self.abort_404_not_found()
        return user

    @flask_login.login_required
    def get(self, user_id):
        """
        ---
        description: Get a user.
        responses:
            "200": "UserEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: user_id
            in: path
            schema:
                type: string
        tags:
          - Users
        """
        user = self._get(user_id)
        return self.serializer.one.dump(user)

    @flask_login.login_required
    def delete(self, user_id):
        """
        ---
        description: Delete a user.
        responses:
            "204": "204"
            "401": "401"
            "404": "404"
        parameters:
          - name: user_id
            in: path
            schema:
                type: string
        tags:
          - Users
        """
        user = self._get(user_id)
        user.delete()
        return self.response_204_no_content()

    @flask_login.login_required
    def put(self, user_id):
        """
        ---
        description: Edit a user.
        responses:
            "200": "UserEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: user_id
            in: path
            schema:
                type: string
        requestBody:
            content:
                application/json:
                    schema: UserUpdate
        tags:
          - Users
        """
        user = self._get(user_id)
        data = self.validate_user(self.schema.update, user)
        password = data.pop("password", None)
        if password:
            user.set_password(password)
        user.update(data)
        return self.serializer.one.dump(user)


class UserListAPI(ApiEndpoint, UserValidationMixin):
    serializer = UserSerializer()
    schema = UserSchema()

    @flask_login.login_required
    def get(self):
        """
        ---
        description: Get a list of users.
        responses:
            "200": "UserList"
            "401": "401"
        tags:
          - Users
        """
        users = User.all()
        return self.serializer.many.dump(users)

    @flask_login.login_required
    def post(self):
        """
        ---
        description: Create a user.
        responses:
            "201": "UserCreated"
            "400": "400"
            "401": "401"
        requestBody:
            content:
                application/json:
                    schema: UserCreate
        tags:
          - Users
        """
        data = self.validate_user(self.schema.create)
        user = User.create(data)
        return self.response_201_created(self.serializer.one.dump(user))


class RegisterSchema(marshmallow.Schema):
    email = marshmallow.fields.Email(required=True)
    password = marshmallow.fields.String(required=True)
    name = marshmallow.fields.String(required=True)
    secret = marshmallow.fields.String(required=True)


class RegisterAPI(ApiEndpoint, UserValidationMixin):
    schema = RegisterSchema()
    serializer = UserSerializer()

    def post(self):
        """
        ---
        description: Sign up for a user account.
        responses:
            "201": "UserCreated"
            "400": "400"
        requestBody:
            content:
                application/json:
                    schema: Register
        tags:
          - Authentication
        """

        data = self.validate_user(self.schema)
        if data.get("secret") != Config.REGISTRATION_KEY:
            message = "Invalid registration key."
            self.abort_400_bad_request({"secret": [message]})
        user = User.create(data)
        return self.response_201_created(self.serializer.one.dump(user))


user_entity_view = UserEntityAPI.as_view("user")
user_list_view = UserListAPI.as_view("users")

rule(
    "/users/",
    view_func=user_list_view,
    methods=["GET", "POST"],
)
rule(
    "/users/<user_id>/",
    view_func=user_entity_view,
    methods=["GET", "DELETE", "PUT"],
)
rule(
    "/register/",
    view_func=RegisterAPI.as_view("register"),
    methods=["POST"],
)

spec.components.schema("UserCreate", schema=UserSchema.create)
spec.components.schema("UserUpdate", schema=UserSchema.update)
spec.components.schema("Register", schema=RegisterSchema)
