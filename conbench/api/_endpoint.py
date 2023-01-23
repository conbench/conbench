import functools
import logging
import os

import flask as f
import flask.views
import flask_login
import marshmallow

log = logging.getLogger(__name__)


def as_bool(x):
    return x.lower() in ["yes", "y", "1", "on", "true"]


def maybe_login_required(func):
    @functools.wraps(func)
    def maybe(*args, **kwargs):
        public = as_bool(os.getenv("BENCHMARKS_DATA_PUBLIC", "yes"))
        if not public:
            return flask_login.login_required(func)(*args, **kwargs)
        return func(*args, **kwargs)

    return maybe


class ApiEndpoint(flask.views.MethodView):
    def validate(self, schema):
        # Emits a 400 response if req does not have expected Content-Type set.
        data = f.request.get_json()

        # Note(JP): replace first-level zero-length string values with
        # None? So that users can pass "" instead of null | non-exist?
        munged = data.copy() if data else data
        for field, value in data.items():
            if isinstance(value, str) and not value.strip():
                munged[field] = None

        try:
            # `schema.load()` (instead of only `schema.validate()`) implies
            # calling post_load hooks if defined.
            result = schema.load(munged)
        except marshmallow.ValidationError as exc:
            # `exc.messages` is equivalent to `errors = schema.validate(data)`
            self.abort_400_bad_request(exc.messages)

        # Note(JP): validation succeeded, but no data was provided. That
        # indicates that there is no required field in the schema that the
        # input data was validated against. Technically, this is a valid
        # noop-update. But it's nicer to tell users that nothing was in fact
        # updated, and return a 4xx response. That specific error message is
        # legacy behavior.
        if not data:
            self.abort_400_bad_request({"_errors": ["Empty request body."]})

        return result

    def redirect(self, endpoint, **kwargs):
        return f.redirect(f.url_for(endpoint, **kwargs))

    def abort_400_bad_request(self, message):
        if not isinstance(message, dict):
            message = {"_errors": [message]}
        f.abort(400, description=message)

    def abort_404_not_found(self):
        f.abort(404)

    def response_204_no_content(self):
        return "", 204

    def response_202_accepted(self):
        return "", 202

    def response_201_created(self, body):
        headers = {
            "Content-Type": "application/json",
            "Location": body["links"]["self"],
        }
        return body, 201, headers
