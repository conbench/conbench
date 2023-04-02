def test_robots_txt(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.text == "User-Agent: *\nDisallow: /"


def test_user_agent_denylist(client):
    for path in ("/api/ping/", "/", "/api/runs/"):
        resp = client.get(path)
        assert resp.status_code == 403
