import os

import flask as f
import flask.views
import flask_login


def as_bool(x):
    return x.lower() in ["yes", "y", "1", "on", "true"]


class AppEndpoint(flask.views.MethodView):
    def public_data_off(self):
        public = as_bool(os.getenv("BENCHMARKS_DATA_PUBLIC", "yes"))
        return not flask_login.current_user.is_authenticated and not public

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
