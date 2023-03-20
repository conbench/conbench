import logging
from urllib.parse import urljoin

import pytest
import requests
from bs4 import BeautifulSoup

from ...config import TestConfig
from ...tests.app import _asserts

log = logging.getLogger(__name__)


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


class TestLoginOIDC(_asserts.AppEndpointTest):
    def test_login_page_shows_sso_link(self, client):
        # In the test suite the "Google Login" link is currently expected to
        # show because GOOGLE_CLIENT_ID is set. Note that this label should
        # change into something more generic or into a value configured by the
        # operator.
        r = client.get("/login/", follow_redirects=True)
        assert "Google Login" in r.text

    def test_login_link_carries_target_param(self, client):
        # When rendering the login page with a `target` query parameter, expect
        # the same parameter to be added to the rendered SSO login link,
        # example: <a href="/api/google/?target=bubaz">Google Login</a>
        r = client.get("/login/?target=bubaz")
        assert "target=bubaz" in r.text

    @pytest.mark.parametrize(
        "target_url",
        [
            None,
            "/relative",
            "https://rofl.com",
            "https://foo.bar?x=y",
            # Test a literal %20 and a literal %2F to be carried across the
            # flow. This is a good way to find flaws in the
            # URL-encoding-decoding information flow (the goal is that these
            # character sequences are communicated verbatim, i.e. end up being
            # emitted as-is in the final redirect URL).
            "https://foo.bar/path/?x=%20yz",
            "https://foo.bar/path/?x=y%2Fz",
        ],
    )
    def test_oidc_flow_against_dex(self, client, target_url):
        # TODO: parse this 'initiate flow URL' from the HTML login page, i.e.
        # from the button/ link that people would actually click. If that is a
        # _relative_ href then construct an absolute URL from it (see below).

        # As long as `client` is the Flask test client we do not use an actual
        # HTTP client/server interaction. The URL here must be specified in
        # absolute terms because the request handler uses scheme, host, port to
        # dynamically generate the OIDC callback URL. We could set any scheme
        # and host, but we want to match the allow-listed callback URL that Dex
        # is aware of. That is is currently set to
        # http://127.0.0.1:5000/api/google/callback -- see
        # containders/dex/config.yml
        if target_url is None:
            r0 = client.get("http://127.0.0.1:5000/api/google/")
        else:
            # The slash before the question mark is required, otherwise Flask
            # will emit a 308 redirect to the slashy version first. Note that
            # when manually putting the URL together like this there is no
            # URL-encoding happening on the query string. In the Werkzeug test
            # client automatic construction of a URL query string is done by
            # providing the `query_string` arg with a dictionary as value --
            # URL-encoding is then automatically done by the client before
            # sending the request.
            r0 = client.get(
                "http://127.0.0.1:5000/api/google/", query_string={"target": target_url}
            )

        # `r0` is meant to be a redirect response, redirecting to the identity
        # provider.  The redirect is expected to be delivered via a 302
        # response.
        assert r0.status_code == 302, f"unexpected response: {r0.text}"

        # Extract the full URL we've been redirected to. The URL
        # represents a so-called authorization request, with all the parameters
        # for that request being encoded in the URL query parameters
        authorization_request_url = r0.headers["location"]
        log.info(f"{authorization_request_url=}")

        # Emit authorization request against identity provider.
        r1 = requests.get(authorization_request_url)

        # We are not yet logged in to the identity provider which is why
        # we expect it to send a login page in the response. That login
        # page shows an email/password login form. Extract form submission
        # endpoint URL from login page. It's a relative URL.
        assert r1.status_code == 200, f"bad response: {r1.text}"
        rel_login_post_url = parse_login_page(r1.text)
        log.info("rel_login_post_url: %s", rel_login_post_url)

        # Construct absolute form submission endpoing URL. urljoin() will
        # pick only scheme and DNS name from the authorization_request_url
        # because the rel_login_post_url is expected to start with a slash.
        login_post_url = urljoin(authorization_request_url, rel_login_post_url)

        # Defined in Dex' static configuration document.
        login_form_data = {
            "login": "admin@example.com",
            "password": "password",
        }

        log.info("login_post_url: %s", login_post_url)
        log.info("login_form_data: %s", login_form_data)
        r2 = requests.post(login_post_url, data=login_form_data)
        log.info("response to POSTing credentials: %s", r2.status_code)

        # When bad credentials are provided the response status code is
        # still 200, with this text in the HTML doc:
        assert "Invalid Email Address and password" not in r2.text

        # `r2.text` is expected to be an HTML document containing the
        # consent form. Parse the document and POST the form data to the
        # same endpoint that served it.
        consent_form_data = parse_consent_review_page(r2.text)

        # Extract the full URL for the endpoint that served the consent
        # form from the previous response.
        consent_post_url = r2.url

        log.info("consent_post_url: %s", consent_post_url)
        log.info("consent_form_data: %s", consent_form_data)
        log.info("post consent form")
        r3 = requests.post(
            consent_post_url, data=consent_form_data, allow_redirects=False
        )

        # Upon success, the response emitted by Dex redirects back to the
        # relying party (Conbench) which (in the back-channel) communicates
        # with the OP (Dex) and eventually emits the authentication proof
        assert str(r3.status_code).startswith("3")
        callback_request_url = r3.headers["location"]
        log.info(f"{callback_request_url=}")

        # In this test suite the web application is not exposed by a real HTTP
        # server. It can only be reached with the test client `client` -- which
        # seems to deal fine with the absolute nature of
        # `callback_request_url`.
        r4 = client.get(callback_request_url)
        # The expected response is a 302 redirect response.
        assert r4.status_code == 302, f"bad response: {r4.text}"
        log.info(r4.headers)

        # Confirm that the api has returned authentication proof.
        assert "set-cookie" in r4.headers
        assert "session" in r4.headers["set-cookie"]

        if target_url is None:
            assert r4.headers["location"] == "/"
        else:
            assert r4.headers["location"] == target_url


def parse_login_page(html):
    """Parse HTML, extract all info required for form submission.
    If the `connectors` enumeration in Dex' config.yaml is empty, then this
    landing page presents a form. If it is not empty, then this landing page
    requires selecting one of the connectors. Rely on no connectors being
    defined.
    """
    page = BeautifulSoup(html, features="lxml")

    # Dex emits just a relative POST URL in the login HTML doc.
    rel_post_url = page.find("form")["action"]

    return rel_post_url


def parse_consent_review_page(html):
    """Parse HTML, extract all info required for form submission.
    Form example:
            <form method="post">
            <input type="hidden" name="req" value="vinfxhadooorlhxikzae"/>
            <input type="hidden" name="approval" value="approve">
            <button type="submit" class="dex-btn theme-btn--success">
                <span class="dex-btn-text">Grant Access</span>
            </button>
            </form>
    """
    page = BeautifulSoup(html, features="lxml")
    form_data = {
        "approval": "approve",
        "req": page.find("input", attrs={"name": "req"})["value"],
    }

    return form_data
