expected_text = """
User-Agent: *
Allow: /
"""


def test_robots(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == expected_text
def test_user_agent_denylist(client):
    for path in ("/api/ping/", "/", "/api/runs/"):
        resp = client.get(path)
        assert resp.status_code == 403
