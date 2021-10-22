from ...entities.user import User


def test_user_repr():
    user = User(name="Gwen Clarke", email="gwen@example.com")
    assert repr(user) == "<User gwen@example.com>"


def test_user_str():
    user = User(name="Gwen Clarke", email="gwen@example.com")
    assert str(user) == "<User gwen@example.com>"
