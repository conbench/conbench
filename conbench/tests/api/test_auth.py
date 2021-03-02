import copy

from ...tests.api import _asserts


class TestLoginPost(_asserts.PostEnforcer):
    url = "/api/login/"
    required_fields = ["email", "password"]
    valid_payload = {"email": "fixture@example.com", "password": "fixture"}

    def test_unauthenticated(self, client):
        self._create_fixture_user()

        # cannot get users before login
        response = client.get("/api/users/")
        self.assert_401_unauthorized(response)

        # login
        response = client.post("/api/login/", json=self.valid_payload)
        self.assert_204_no_content(response)

        # can get users after login
        response = client.get("/api/users/")
        self.assert_200_ok(response)

    def test_already_authenticated_good_credentials(self, client):
        # already logged in
        self.authenticate(client)

        # can get users before re-login
        response = client.get("/api/users/")
        self.assert_200_ok(response)

        # login
        response = client.post("/api/login/", json=self.valid_payload)
        self.assert_204_no_content(response)

        # can get users after re-login
        response = client.get("/api/users/")
        self.assert_200_ok(response)

    def test_already_authenticated_bad_credentials(self, client):
        # already logged in
        self.authenticate(client)

        # can get users before re-login
        response = client.get("/api/users/")
        self.assert_200_ok(response)

        # login (with bad credentials)
        data = copy.deepcopy(self.valid_payload)
        data["password"] = "wrong"
        response = client.post("/api/login/", json=data)
        message = {"_errors": ["Invalid email or password."]}
        self.assert_400_bad_request(response, message)

        # cannot get users after bad re-login
        response = client.get("/api/users/")
        self.assert_401_unauthorized(response)

    def test_bad_credentials(self, client):
        data = self.valid_payload.copy()
        data["password"] = "wrong"
        response = client.post("/api/login/", json=data)
        message = {"_errors": ["Invalid email or password."]}
        self.assert_400_bad_request(response, message)

    def test_unknown_email(self, client):
        data = self.valid_payload.copy()
        data["email"] = "unknown@example.com"
        response = client.post("/api/login/", json=data)
        message = {"_errors": ["Invalid email or password."]}
        self.assert_400_bad_request(response, message)

    def test_invalid_email_address(self, client):
        data = self.valid_payload.copy()
        data["email"] = "not-an-email-address"
        response = client.post("/api/login/", json=data)
        message = {"email": ["Not a valid email address."]}
        self.assert_400_bad_request(response, message)


class TestLogoutGet(_asserts.ApiEndpointTest):
    def test_authenticated(self, client):
        self.authenticate(client)

        # can get users before logout
        response = client.get("/api/users/")
        self.assert_200_ok(response)

        # logout
        response = client.get("/api/logout/")
        self.assert_204_no_content(response)

        # cannot get users after logout
        response = client.get("/api/users/")
        self.assert_401_unauthorized(response)

    def test_unauthenticated(self, client):
        # cannot get users before logout
        response = client.get("/api/users/")
        self.assert_401_unauthorized(response)

        # logout
        response = client.get("/api/logout/")
        self.assert_204_no_content(response)

        # cannot get users after logout
        response = client.get("/api/users/")
        self.assert_401_unauthorized(response)
