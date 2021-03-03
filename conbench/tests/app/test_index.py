from ...tests.app import _asserts


class TestIndex(_asserts.AppEndpointTest):
    def test_unknown_endpoint(self, client):
        response = client.get("/foo/")
        self.assert_404_not_found(response)

    def test_index_authenticated(self, client):
        self.authenticate(client)
        response = client.get("/")
        self.assert_index_page(response)
        response = client.get("/index/")
        self.assert_index_page(response)

    def test_index_unauthenticated(self, client):
        response = client.get("/", follow_redirects=True)
        self.assert_index_page(response)
        response = client.get("/index/", follow_redirects=True)
        self.assert_index_page(response)
