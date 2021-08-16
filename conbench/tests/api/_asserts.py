import copy

from ...api._errors import ErrorSchema
from ...tests.helpers import _create_fixture_user, create_random_user


class ApiEndpointTest:
    fixture_user = None

    def authenticate(self, client):
        self.fixture_user = self._create_fixture_user()
        self.login(client, "fixture@example.com", "fixture")

    def login(self, client, email, password):
        data = {"email": email, "password": password}
        client.post("/api/login/", json=data)

    def create_random_user(self):
        return create_random_user()

    def _create_fixture_user(self):
        return _create_fixture_user()

    def assert_200_ok(self, r, expected=None, contains=None):
        assert r.status_code == 200, r.status_code
        assert r.content_type == "application/json", r.content_type
        if expected:
            assert r.json == expected, r.json
        if contains:
            assert contains in r.json

    def assert_201_created(self, r, expected, location):
        assert r.status_code == 201, r.status_code
        assert r.content_type == "application/json", r.content_type
        assert r.location == location, r.location
        assert r.json == expected, r.json

    def assert_202_accepted(self, r):
        assert r.status_code == 202, r.status_code
        assert r.json is None, r.json

    def assert_204_no_content(self, r):
        assert r.status_code == 204, r.status_code
        # TODO: assert r.content_type == "application/json", r.content_type
        assert r.json is None, r.json

    def assert_400_bad_request(self, r, message):
        assert r.status_code == 400, r.status_code
        assert r.content_type == "application/json", r.content_type
        assert r.json == {
            "code": 400,
            "name": "Bad Request",
            "description": message,
        }, r.json
        # TODO: https://github.com/marshmallow-code/marshmallow/issues/120
        # errors = BadRequestSchema().validate(r.json)
        # assert errors == {}, errors

    def assert_401_unauthorized(self, r):
        assert r.status_code == 401, r.status_code
        assert r.content_type == "application/json", r.content_type
        assert r.json == {"code": 401, "name": "Unauthorized"}, r.json
        errors = ErrorSchema().validate(r.json)
        assert errors == {}, errors

    def assert_404_not_found(self, r):
        assert r.status_code == 404, r.status_code
        assert r.content_type == "application/json", r.content_type
        assert r.json == {"code": 404, "name": "Not Found"}, r.json
        errors = ErrorSchema().validate(r.json)
        assert errors == {}, errors


class Enforcer(ApiEndpointTest):
    def test_unauthenticated(self, client):
        raise NotImplementedError()


class ListEnforcer(Enforcer):
    def test_unauthenticated(self, client, monkeypatch):
        if getattr(self, "public", False):
            monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
            response = client.get(self.url)
            self.assert_401_unauthorized(response)

            monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "on")
            response = client.get(self.url)
            self.assert_200_ok(response)
        else:
            response = client.get(self.url)
            self.assert_401_unauthorized(response)


class GetEnforcer(Enforcer):
    def test_unauthenticated(self, client, monkeypatch):
        if getattr(self, "public", False):
            entity = self._create()
            entity_url = self.url.format(entity.id)

            monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "off")
            response = client.get(entity_url)
            self.assert_401_unauthorized(response)

            monkeypatch.setenv("BENCHMARKS_DATA_PUBLIC", "on")
            response = client.get(entity_url)
            self.assert_200_ok(response)
        else:
            response = client.get(self.url.format("id"))
            self.assert_401_unauthorized(response)

    def test_unknown(self, client):
        self.authenticate(client)
        response = client.get(self.url.format("unknown"))
        self.assert_404_not_found(response)


class DeleteEnforcer(Enforcer):
    def test_unauthenticated(self, client):
        response = client.delete(self.url.format("id"))
        self.assert_401_unauthorized(response)

    def test_unknown(self, client):
        self.authenticate(client)
        response = client.delete(self.url.format("unknown"))
        self.assert_404_not_found(response)


class PostEnforcer(Enforcer):
    def test_unauthenticated(self, client):
        response = client.post(self.url, json={})
        self.assert_401_unauthorized(response)

    def test_extra_field(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["extra"] = "field"
        response = client.post(self.url, json=data)
        message = {"extra": ["Unknown field."]}
        self.assert_400_bad_request(response, message)

    def test_cannot_set_id(self, client):
        self.authenticate(client)
        data = copy.deepcopy(self.valid_payload)
        data["id"] = "some id"
        response = client.post(self.url, json=data)
        message = {"id": ["Read-only field."]}
        self.assert_400_bad_request(response, message)

    def test_required_fields(self, client):
        self.authenticate(client)
        for field in self.required_fields:
            data = copy.deepcopy(self.valid_payload)
            del data[field]
            response = client.post(self.url, json=data)
            message = {field: ["Missing data for required field."]}
            self.assert_400_bad_request(response, message)

    def test_empty_fields(self, client):
        self.authenticate(client)
        for field in self.valid_payload:
            data = copy.deepcopy(self.valid_payload)
            data[field] = ""
            response = client.post(self.url, json=data)
            message = {field: ["Field may not be null."]}
            self.assert_400_bad_request(response, message)

    def test_whitespace_fields(self, client):
        self.authenticate(client)
        for field in self.valid_payload:
            data = copy.deepcopy(self.valid_payload)
            data[field] = "  \n\n\t\t  "
            response = client.post(self.url, json=data)
            message = {field: ["Field may not be null."]}
            self.assert_400_bad_request(response, message)

    def test_null_fields(self, client):
        self.authenticate(client)
        for field in self.valid_payload:
            data = copy.deepcopy(self.valid_payload)
            data[field] = None
            response = client.post(self.url, json=data)
            message = {field: ["Field may not be null."]}
            self.assert_400_bad_request(response, message)

    def test_empty_payload(self, client):
        self.authenticate(client)
        response = client.post(self.url, json={})
        message = {"_errors": ["Empty request body."]}
        for field in self.required_fields:
            message[field] = ["Missing data for required field."]
        self.assert_400_bad_request(response, message)

    def test_not_application_json(self, client):
        self.authenticate(client)
        response = client.post(self.url, data=self.valid_payload)
        message = {
            "_errors": ["Empty request body."],
            "_schema": [
                "Invalid input type.",
                "Did you specify Content-type: application/json?",
            ],
        }
        self.assert_400_bad_request(response, message)


class PutEnforcer(Enforcer):
    def test_unauthenticated(self, client):
        response = client.put(self.url.format("id"), json={})
        self.assert_401_unauthorized(response)

    def test_unknown(self, client):
        self.authenticate(client)
        response = client.put(self.url.format("unknown"), json={})
        self.assert_404_not_found(response)

    def test_extra_field(self, client):
        self.authenticate(client)
        entity = self._create_entity_to_update()
        data = {"extra": "field"}
        response = client.put(self.url.format(entity.id), json=data)
        message = {"extra": ["Unknown field."]}
        self.assert_400_bad_request(response, message)

    def test_cannot_set_id(self, client):
        self.authenticate(client)
        entity = self._create_entity_to_update()
        data = {"id": "some id"}
        response = client.put(self.url.format(entity.id), json=data)
        message = {"id": ["Read-only field."]}
        self.assert_400_bad_request(response, message)

    def test_empty_fields(self, client):
        self.authenticate(client)
        entity = self._create_entity_to_update()
        for field in self.valid_payload:
            data = copy.deepcopy(self.valid_payload)
            data[field] = ""
            response = client.put(self.url.format(entity.id), json=data)
            message = {field: ["Field may not be null."]}
            self.assert_400_bad_request(response, message)

    def test_whitespace_fields(self, client):
        self.authenticate(client)
        entity = self._create_entity_to_update()
        for field in self.valid_payload:
            data = copy.deepcopy(self.valid_payload)
            data[field] = "  \n\n\t\t  "
            response = client.put(self.url.format(entity.id), json=data)
            message = {field: ["Field may not be null."]}
            self.assert_400_bad_request(response, message)

    def test_null_fields(self, client):
        self.authenticate(client)
        entity = self._create_entity_to_update()
        for field in self.valid_payload:
            data = copy.deepcopy(self.valid_payload)
            data[field] = None
            response = client.put(self.url.format(entity.id), json=data)
            message = {field: ["Field may not be null."]}
            self.assert_400_bad_request(response, message)

    def test_empty_payload(self, client):
        self.authenticate(client)
        entity = self._create_entity_to_update()
        response = client.put(self.url.format(entity.id), json={})
        message = {"_errors": ["Empty request body."]}
        self.assert_400_bad_request(response, message)

    def test_not_application_json(self, client):
        self.authenticate(client)
        entity = self._create_entity_to_update()
        response = client.put(self.url.format(entity.id), data=self.valid_payload)
        message = {
            "_errors": ["Empty request body."],
            "_schema": [
                "Invalid input type.",
                "Did you specify Content-type: application/json?",
            ],
        }
        self.assert_400_bad_request(response, message)
