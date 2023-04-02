def test_robots_txt(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "User-Agent: *\nDisallow: /" in response.text


def test_user_agent_denylist(client):
    for path in ("/api/ping/", "/", "/api/runs/"):
        resp = client.get(path, headers={"User-Agent": "some PetalBot version 1"})
        assert resp.status_code == 403
        assert "unexpected user agent" in resp.text


def test_noindex_directive_in_html(client):
    resp = client.get("/")
    assert '<meta name="robots" content="noindex">' in resp.text
