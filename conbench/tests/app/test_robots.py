def test_robots(self, client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.data == "User-Agent: *\nDisallow: /compare/\n"
