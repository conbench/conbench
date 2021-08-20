import flask as f
import flask_login
import marshmallow
import sqlalchemy as s
import werkzeug.security

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    generate_uuid,
)
from ..extensions import login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


class User(flask_login.UserMixin, Base, EntityMixin):
    __tablename__ = "user"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    email = NotNull(s.String(120), index=True, unique=True)
    name = NotNull(s.String(120))
    password = NotNull(s.String(128))

    def __repr__(self):
        return f"<User {self.email}>"

    def set_password(self, password):
        self.password = werkzeug.security.generate_password_hash(password)

    def check_password(self, password):
        return werkzeug.security.check_password_hash(self.password, password)

    @staticmethod
    def create(data):
        user = User(name=data["name"], email=data["email"])
        user.set_password(data["password"])
        user.save()
        return user


class UserCreate(marshmallow.Schema):
    email = marshmallow.fields.Email(required=True)
    password = marshmallow.fields.String(required=True)
    name = marshmallow.fields.String(required=True)


class UserUpdate(marshmallow.Schema):
    email = marshmallow.fields.Email()
    password = marshmallow.fields.String()
    name = marshmallow.fields.String()


class UserSchema:
    create = UserCreate()
    update = UserUpdate()


class _Serializer(EntitySerializer):
    def _dump(self, user):
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "links": {
                "list": f.url_for("api.users", _external=True),
                "self": f.url_for("api.user", user_id=user.id, _external=True),
            },
        }


class UserSerializer:
    one = _Serializer()
    many = _Serializer(many=True)
