from ...entities.user import User


def foo_user_repr():
    user = User(name="Gwen Clarke", email="gwen@example.com")
    assert repr(user) == "<User gwen@example.com>"


def foo_user_str():
    user = User(name="Gwen Clarke", email="gwen@example.com")
    assert str(user) == "<User gwen@example.com>"
