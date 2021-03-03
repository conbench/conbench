from ...config import TestConfig
from ...tests.app import _asserts


class TestRegister(_asserts.AppEndpointTest):
    def test_get_register_page_authenticated(self, client):
        self.authenticate(client)
        response = client.get("/register/", follow_redirects=True)
        self.assert_index_page(response)

    def test_register(self, client):
        # go to register page
        response = client.get("/register/")
        self.assert_registration_page(response)

        # register
        data = {
            "email": "register@example.com",
            "name": "Register",
            "password": "register",
            "password2": "register",
            "secret": TestConfig.REGISTRATION_KEY,
            "csrf_token": self.get_csrf_token(response),
        }
        response = client.post("/register/", data=data, follow_redirects=True)
        self.assert_login_page(response)

        # make sure you can login with this new user
        data = {
            "email": "register@example.com",
            "password": "register",
            "remember_me": True,
            "csrf_token": self.get_csrf_token(response),
        }
        response = client.post("/login/", data=data, follow_redirects=True)
        self.assert_index_page(response)

    def test_email_address_already_in_use(self, client):
        other = self.create_random_user()

        # go to register page
        response = client.get("/register/")
        self.assert_registration_page(response)

        # register
        data = {
            "email": other.email,
            "name": "Register",
            "password": "register",
            "password2": "register",
            "secret": TestConfig.REGISTRATION_KEY,
            "remember_me": True,
            "csrf_token": self.get_csrf_token(response),
        }
        response = client.post("/register/", data=data, follow_redirects=True)

        # registration failed (still on the registration page)
        self.assert_registration_page(response)
        assert b"Email address already in use." in response.data


class TestLogin(_asserts.AppEndpointTest):
    def test_get_login_page_authenticated(self, client):
        self.authenticate(client)
        response = client.get("/login/", follow_redirects=True)
        self.assert_index_page(response)

    def test_login(self, client):
        self._create_fixture_user()

        # go to login page
        response = client.get("/login/")
        self.assert_login_page(response)

        # login submit
        data = {
            "email": "fixture@example.com",
            "password": "fixture",
            "csrf_token": self.get_csrf_token(response),
        }
        response = client.post("/login/", data=data, follow_redirects=True)
        self.assert_index_page(response)

    def test_login_failed(self, client):
        other = self.create_random_user()

        # go to login page
        response = client.get("/login/")
        self.assert_login_page(response)

        # login submit
        data = {
            "email": other.email,
            "password": "wrong",
            "csrf_token": self.get_csrf_token(response),
        }
        response = client.post("/login/", data=data, follow_redirects=True)

        # login failed (still on the login page)
        self.assert_login_page(response)
        assert b"Invalid email or password." in response.data


class TestLogout(_asserts.AppEndpointTest):
    def test_logout_authenticated(self, client):
        self.authenticate(client)

        # can get users page before
        response = client.get("/users/", follow_redirects=True)
        self.assert_page(response, "Users")

        # logout
        response = client.get("/logout/", follow_redirects=True)
        self.assert_index_page(response)

        # cannot get users page after
        response = client.get("/users/", follow_redirects=True)
        self.assert_login_page(response)

    def test_logout_unauthenticated(self, client):
        # cannot get users page before
        response = client.get("/users/", follow_redirects=True)
        self.assert_login_page(response)

        # logout
        response = client.get("/logout/", follow_redirects=True)
        self.assert_index_page(response)

        # cannot get users page after
        response = client.get("/users/", follow_redirects=True)
        self.assert_login_page(response)
