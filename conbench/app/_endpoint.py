import logging
import os

import flask as f
import flask.views
import flask_login

from flask import Response


from typing import Optional

log = logging.getLogger(__name__)


def as_bool(x):
    return x.lower() in ["yes", "y", "1", "on", "true"]


class AppEndpoint(flask.views.MethodView):
    def authorize_or_terminate(self) -> Optional[Response]:
        """
        Inspect request and application config. Make an access control decision
        and enforce it. If access is denied then this function generates a
        `Response` object which signals to the caller that it must _terminate_
        request handling by emitting that response to the user agent.
        """

        if self._should_access_be_denied():
            # Redirect user to the login page. Set a query parameter `target`
            # with the value set to the _relative_ URL the user tried to
            # access, retaining all query arguments of that URL. This allows
            # for the login machinery to redirect the user back to where they
            # actually wanted to go (after successful login). Flask's
            # `full_path` on the request object is documented as "requested
            # path, including the query string."
            if f.request.full_path != "/":
                log.info("authorizer for url: %s", f.request.full_path)
                return self.redirect("app.login", target=f.request.full_path)
            else:
                return self.redirect("app.login")

        # Explicit None: caller is OK to proceed.
        return None

    def public_data_off(self):
        # An alias, to not break old code.
        return self._should_access_be_denied()

    def _should_access_be_denied(self):
        """
        Inspect authentication state of the incoming request. Compute whether
        data/view should be hidden (return `True`) or not (return `False`).

        When BENCHMARKS_DATA_PUBLIC is set to a true-ish value then always show
        benchmark data (regardless of whether the request is anonymous or not).

        When BENCHMARK_DATA_PUBLIC is set to a false-ish value then decide to
        hide the view (return True) when the access is from anonymous.

        Note, just a quick thought dump: this needs a bit of consolidation for
        easier code readability, and for de-duplicating per-view code. In
        individual views this method is so far used to short-cut request
        processing and redirect to the login page if needed. Maybe build a
        simple decorator instead with a name that relates to access control
        (such as `enforce_access_control()`). Decorated views enforce access
        control (with the business logic as in _this_ function here),
        non-decorated views do not enforce. If access is denied then the
        redirect to the login page should be emitted from that decorator -- the
        redirect will contain view-specific parameters (target URL).
        """

        # TODO(JP): the environment variable readout should be managed via the
        # config.py module, and here we should only access the app's config
        # object. So that config.py can be the place that pragmatically
        # documents all supported environment variables and their meaning.
        # I see that tests make use of mocking this, i.e. changing behavior
        # is a little bit of work.
        is_public = as_bool(os.getenv("BENCHMARKS_DATA_PUBLIC", "yes"))

        if is_public:
            # Never hide.
            return False

        if flask_login.current_user.is_authenticated:
            # Non-anonymous access: do not hide
            return False

        # Anonymous access: hide.
        return True

    def redirect(self, endpoint, **kwargs):
        return f.redirect(f.url_for(endpoint, **kwargs))

    def render_template(self, template, **kwargs):
        return f.render_template(template, **kwargs)

    def flash(self, *args):
        return f.flash(*args)

    def api_post(self, endpoint, form, **kwargs):
        client = self._get_client()
        response = client.post(f.url_for(endpoint, **kwargs), json=self.data(form))
        if response.status_code == 400:
            self.extend_form_errors(response, form)
        return response

    def api_put(self, endpoint, form, **kwargs):
        client = self._get_client()
        response = client.put(f.url_for(endpoint, **kwargs), json=self.data(form))
        if response.status_code == 400:
            self.extend_form_errors(response, form)
        return response

    def api_delete(self, endpoint, **kwargs):
        client = self._get_client()
        return client.delete(f.url_for(endpoint, **kwargs))

    def api_get(self, endpoint, **kwargs):
        client = self._get_client()
        return client.get(f.url_for(endpoint, **kwargs))

    def api_get_url(self, url):
        client = self._get_client()
        return client.get(url)

    def _get_client(self):
        # TODO: is there any reason not to use test_client in prod?
        client = f.current_app.test_client()
        if flask_login.current_user.is_authenticated:
            current_user_id = flask_login.current_user.id
            with client.session_transaction():
                # TODO: hardcoded "session" etc
                client.set_cookie(
                    "session",
                    "remember_token",
                    flask_login.encode_cookie(current_user_id),
                )
        return client

    def extend_form_errors(self, response, form):
        description = response.json.get("description", {})
        for field in description:
            form_field = getattr(form, field, None)
            if form_field:
                form_field.errors.extend(description[field])
