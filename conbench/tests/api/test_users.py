import copy

import pytest

from ...api._examples import _api_user_entity
from ...config import TestConfig
from ...entities._entity import NotFound
from ...entities.user import User
from ...tests.api import _asserts


def _expected_entity(user):
    return _api_user_entity(user)


class TestUserGet(_asserts.GetEnforcer):
    url = "/api/users/{}/"

    def test_get_user(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        response = client.get(f"/api/users/{other.id}/")
        self.assert_200_ok(response, _expected_entity(other))


class TestUserDelete(_asserts.DeleteEnforcer):
    url = "/api/users/{}/"

    def test_delete_user(self, client):
        self.authenticate(client)
        other = self.create_random_user()

        # can get before delete
        User.one(id=other.id)

        # delete
        response = client.delete(f"/api/users/{other.id}/")
        self.assert_204_no_content(response)

        # cannot get after delete
        with pytest.raises(NotFound):
            User.one(id=other.id)


class TestUserList(_asserts.ListEnforcer):
    url = "/api/users/"

    def test_user_list(self, client):
        self.authenticate(client)
        response = client.get("/api/users/")
        self.assert_200_ok(response, contains=_expected_entity(self.fixture_user))


class TestUserPost(_asserts.PostEnforcer):
    url = "/api/users/"
    required_fields = ["email", "password", "name"]
    valid_payload = {
        "email": "new@example.com",
        "password": "new",
        "name": "New name",
    }

    def setup(self):
        User.delete_all()

    def test_create_user(self, client):
        self.authenticate(client)
        response = client.post("/api/users/", json=self.valid_payload)
        new_id = response.json["id"]
        user = User.one(id=new_id)
        location = "http://localhost/api/users/%s/" % new_id
        self.assert_201_created(response, _expected_entity(user), location)

    def test_invalid_email_address(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["email"] = "not an email address"
        response = client.post("/api/users/", json=data)
        message = {"email": ["Not a valid email address."]}
        self.assert_400_bad_request(response, message)

    def test_duplicate_email_address(self, client):
        self.authenticate(client)
        client.post("/api/users/", json=self.valid_payload)
        response = client.post("/api/users/", json=self.valid_payload)
        message = {"email": ["Email address already in use."]}
        self.assert_400_bad_request(response, message)


class TestUserPut(_asserts.PutEnforcer):
    url = "/api/users/{}/"
    valid_payload = {
        "email": "updated@example.com",
        "password": "updated",
        "name": "Updated name",
    }

    def setup(self):
        User.delete_all()

    def _create_entity_to_update(self):
        user = User(name="Bryce", email="bryce@example.com")
        user.set_password("yerba mate")
        user.save()
        return user

    def test_update_one_field(self, client):
        self.authenticate(client)

        # before
        before = User.one(id=self.fixture_user.id)
        assert before.name == "Fixture name"
        assert before.email == "fixture@example.com"
        assert before.check_password("fixture")

        # update name
        data = {"name": "Updated name"}
        response = client.put(f"/api/users/{self.fixture_user.id}/", json=data)

        # after
        after = User.one(id=self.fixture_user.id)
        self.assert_200_ok(response, _expected_entity(after))
        assert after.name == "Updated name"
        assert after.email == "fixture@example.com"
        assert after.check_password("fixture")

    def test_update_all_fields(self, client):
        self.authenticate(client)

        # before
        before = User.one(id=self.fixture_user.id)
        assert before.name == "Fixture name"
        assert before.email == "fixture@example.com"
        assert before.check_password("fixture")

        # update
        data = self.valid_payload
        response = client.put(f"/api/users/{self.fixture_user.id}/", json=data)

        # after
        after = User.one(id=self.fixture_user.id)
        self.assert_200_ok(response, _expected_entity(after))
        assert after.name == "Updated name"
        assert after.email == "updated@example.com"
        assert after.check_password("updated")

    def test_invalid_email_address(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        data = copy.deepcopy(self.valid_payload)
        data["email"] = "not an email address"
        response = client.put(f"/api/users/{other.id}/", json=data)
        message = {"email": ["Not a valid email address."]}
        self.assert_400_bad_request(response, message)

    def test_duplicate_email_address(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        data = {"email": self.fixture_user.email}
        response = client.put(f"/api/users/{other.id}/", json=data)
        message = {"email": ["Email address already in use."]}
        self.assert_400_bad_request(response, message)

    def test_unchanged_email_address(self, client):
        self.authenticate(client)
        other = self._create_entity_to_update()
        data = {"email": other.email}
        response = client.put(f"/api/users/{other.id}/", json=data)
        self.assert_200_ok(response, _expected_entity(other))


class TestRegisterPost(_asserts.PostEnforcer):
    url = "/api/register/"
    required_fields = ["email", "password", "name", "secret"]
    valid_payload = {
        "email": "casey@example.com",
        "password": "valorant",
        "name": "Casey",
        "secret": TestConfig.REGISTRATION_KEY,
    }

    def setup(self):
        User.delete_all()

    def test_register(self, client):
        self.authenticate(client)
        response = client.post("/api/register/", json=self.valid_payload)
        new_id = response.json["id"]
        user = User.one(id=new_id)
        location = "http://localhost/api/users/%s/" % new_id
        self.assert_201_created(response, _expected_entity(user), location)

    def test_unauthenticated(self, client):
        response = client.post("/api/register/", json=self.valid_payload)
        new_id = response.json["id"]
        user = User.one(id=new_id)
        location = "http://localhost/api/users/%s/" % new_id
        self.assert_201_created(response, _expected_entity(user), location)

    def test_invalid_secret(self, client):
        data = copy.deepcopy(self.valid_payload)
        data["secret"] = "not the right registration code"
        response = client.post("/api/register/", json=data)
        message = {"secret": ["Invalid registration key."]}
        self.assert_400_bad_request(response, message)

    def test_invalid_email_address(self, client):
        data = copy.deepcopy(self.valid_payload)
        data["email"] = "not an email address"
        response = client.post("/api/register/", json=data)
        message = {"email": ["Not a valid email address."]}
        self.assert_400_bad_request(response, message)

    def test_duplicate_email_address(self, client):
        client.post("/api/register/", json=self.valid_payload)
        response = client.post("/api/register/", json=self.valid_payload)
        message = {"email": ["Email address already in use."]}
        self.assert_400_bad_request(response, message)
