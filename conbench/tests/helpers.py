import uuid

from ..entities.user import User


def _uuid():
    return uuid.uuid4().hex


def _create_fixture_user():
    email = "fixture@example.com"
    user = User.first(email=email)
    if user is None:
        user = User(name="Fixture name", email=email)
        user.set_password("fixture")
        user.save()
    return user


def create_random_user():
    prefix = uuid.uuid4().hex
    email = f"{prefix}@example.com"
    user = User(name=f"{prefix} Name", email=email)
    user.set_password(prefix)
    user.save()
    return user
