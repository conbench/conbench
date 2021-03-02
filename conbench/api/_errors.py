import marshmallow

from ..api._docs import spec


class ErrorSchema(marshmallow.Schema):
    code = marshmallow.fields.Int(description="HTTP error code", required=True)
    name = marshmallow.fields.String(description="HTTP error name", required=True)


class ValidationSchema(marshmallow.Schema):
    _errors = marshmallow.fields.List(
        marshmallow.fields.String,
        description="Validation error messages",
        required=False,
    )
    _schema = marshmallow.fields.List(
        marshmallow.fields.String, description="Schema error messages", required=False
    )


class BadRequestSchema(ErrorSchema):
    description = marshmallow.fields.Nested(
        ValidationSchema,
        description="Additional information about the bad request",
        required=False,
    )


spec.components.schema("Error", schema=ErrorSchema)
spec.components.schema("ErrorValidation", schema=ValidationSchema)
spec.components.schema("ErrorBadRequest", schema=BadRequestSchema)
