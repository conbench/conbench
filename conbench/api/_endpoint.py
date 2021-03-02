import flask as f
import flask.views


class ApiEndpoint(flask.views.MethodView):
    def validate(self, schema):
        data = f.request.get_json(silent=True)

        munged = data.copy() if data else data
        if data:
            for field, value in data.items():
                if isinstance(value, str) and not value.strip():
                    munged[field] = None

        errors = schema.validate(munged)

        if errors:
            hint = "Did you specify Content-type: application/json?"
            if "Invalid input type." in errors.get("_schema", []):
                errors["_schema"].append(hint)

        if not data:
            errors["_errors"] = ["Empty request body."]

        if errors:
            if "id" in errors and errors["id"] == ["Unknown field."]:
                errors["id"] = ["Read-only field."]
            self.abort_400_bad_request(errors)

        return data

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
