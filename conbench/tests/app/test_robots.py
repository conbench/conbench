expected_text = """
User-Agent: *
Disallow: /
"""


def test_robots(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == expected_text
