from ...tests.app import _asserts


class TestUsers(_asserts.AppEndpointTest):
    def test_user_list_authenticated(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        response = client.get("/users/")
        self.assert_page(response, "Users")
        assert "{}</td>".format(other.email).encode() in response.data

    def test_user_list_unauthenticated(self, client):
        response = client.get("/users/", follow_redirects=True)
        self.assert_login_page(response)


class TestUser(_asserts.AppEndpointTest):
    def test_user_get_authenticated(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        response = client.get(f"/users/{other.id}/")
        self.assert_page(response, "User")
        assert 'value="{}"'.format(other.name).encode() in response.data

    def test_user_get_unauthenticated(self, client):
        other = self.create_random_user()
        response = client.get(f"/users/{other.id}/", follow_redirects=True)
        self.assert_login_page(response)

    def test_user_get_unknown(self, client):
        self.authenticate(client)
        response = client.get("/users/unknown/", follow_redirects=True)
        self.assert_index_page(response)
        assert b"Error getting user." in response.data

    def test_user_update_authenticated(self, client):
        self.authenticate(client)
        other = self.create_random_user()

        # go to user page
        response = client.get(f"/users/{other.id}/")
        self.assert_page(response, "User")

        # update user
        data = {
            "name": "New Name",
            "email": other.email,
            "csrf_token": self.get_csrf_token(response),
        }
        response = client.post(f"/users/{other.id}/", data=data, follow_redirects=True)
        self.assert_page(response, "User")
        assert b"User updated." in response.data
        assert b'value="New Name"' in response.data

    def test_user_update_unauthenticated(self, client):
        other = self.create_random_user()
        response = client.post(f"/users/{other.id}/", data={}, follow_redirects=True)
        self.assert_login_page(response)

    def test_user_update_no_csrf_token(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        response = client.post(f"/users/{other.id}/", data={})
        self.assert_page(response, "User")
        assert b"The CSRF token is missing." in response.data
        # TODO: assert name not updated?

    def test_user_update_failed(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        response = client.post(f"/users/{other.id}/", data={"email": "Not an email"})
        self.assert_page(response, "User")
        assert b"Invalid email address." in response.data

    def test_user_delete_authenticated(self, client):
        self.authenticate(client)
        other = self.create_random_user()

        # can get user before
        response = client.get(f"/users/{other.id}/")
        self.assert_page(response, "User")
        assert 'value="{}"'.format(other.name).encode() in response.data

        # delete user
        data = {"delete": ["Delete"], "csrf_token": self.get_csrf_token(response)}
        response = client.post(f"/users/{other.id}/", data=data, follow_redirects=True)
        self.assert_page(response, "Users")
        assert b"User deleted." in response.data

        # cannot get user after
        response = client.get(f"/users/{other.id}/", follow_redirects=True)
        self.assert_index_page(response)
        assert b"Error getting user." in response.data

    def test_user_delete_unauthenticated(self, client):
        other = self.create_random_user()
        data = {"delete": ["Delete"]}
        response = client.post(f"/users/{other.id}/", data=data, follow_redirects=True)
        self.assert_login_page(response)

    def test_user_delete_no_csrf_token(self, client):
        self.authenticate(client)
        other = self.create_random_user()
        data = {"delete": ["Delete"]}
        response = client.post(f"/users/{other.id}/", data=data, follow_redirects=True)
        self.assert_page(response, "User")
        assert b"The CSRF token is missing." in response.data
        # TODO: test user not deleted?


class TestUserCreate(_asserts.AppEndpointTest):
    def test_user_create_get_authenticated(self, client):
        self.authenticate(client)
        response = client.get("/users/create/")
        self.assert_page(response, "User Create")

    def test_user_create_get_unauthenticated(self, client):
        response = client.get("/users/create/", follow_redirects=True)
        self.assert_login_page(response)

    def test_user_create_post_authenticated(self, client):
        self.authenticate(client)

        # go to user create page
        response = client.get("/users/create/")
        self.assert_page(response, "User Create")

        # create user
        data = {
            "email": "new@example.com",
            "name": "New user",
            "password": "password",
            "csrf_token": self.get_csrf_token(response),
        }
        response = client.post("/users/create/", data=data, follow_redirects=True)
        self.assert_page(response, "Users")
        assert b"User created." in response.data

    def test_user_create_post_unauthenticated(self, client):
        response = client.post("/users/create/", data={}, follow_redirects=True)
        self.assert_login_page(response)

    def test_user_create_post_no_csrf_token(self, client):
        self.authenticate(client)
        response = client.post("/users/create/", data={})
        self.assert_page(response, "User Create")
        assert b"The CSRF token is missing." in response.data
