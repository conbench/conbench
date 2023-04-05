import flask


def resp400(description: str) -> flask.Response:
    """
    Utility for canonical generation of 400 Bad Request response with an
    error description. Define elsewhere once used elsewhere.
    """
    return flask.make_response(
        # This puts a JSON body into the response with a JSON object with one
        # key, the description
        flask.jsonify(description=description),
        400,
    )


def json_response_for_byte_sequence(data: bytes, status_code: int) -> flask.Response:
    # Note(JP): it's documented that a byte sequence can be passed in:
    # https://flask.palletsprojects.com/en/2.2.x/api/#flask.Flask.make_response
    return flask.make_response(
        (data, status_code, {"content-type": "application/json"})
    )
