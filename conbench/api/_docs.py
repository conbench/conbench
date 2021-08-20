import apispec
import apispec.ext.marshmallow
import apispec_webframeworks.flask

from ..api import _examples as ex
from ..config import Config

spec = apispec.APISpec(
    title=Config.APPLICATION_NAME,
    version="1.0.0",
    openapi_version="3.0.2",
    plugins=[
        apispec_webframeworks.flask.FlaskPlugin(),
        apispec.ext.marshmallow.MarshmallowPlugin(),
    ],
    servers=[{"url": "http://localhost:5000/"}],
)


example2 = {
    "code": 400,
    "description": {"extra": ["Unknown field."]},
    "name": "Bad Request",
}


def _error(error, example, schema=None):
    content = {"example": example}
    if schema:
        content = {"schema": schema, "example": example}
    return {"description": error, "content": {"application/json": content}}


def _200_ok(example, schema=None):
    content = {"example": example}
    if schema:
        content = {"schema": schema, "example": example}
    return {"description": "OK", "content": {"application/json": content}}


def _201_created(example, schema=None):
    content = {"example": example}
    if schema:
        content = {"schema": schema, "example": example}
    return {
        "description": "Created \n\n The resulting entity URL is returned in the Location header.",
        "content": {"application/json": content},
        #         "headers": {
        #             "Location": {"description": "The new entity URL.", "type": "url"}
        #         },
    }


spec.components.response("200", {"description": "OK"})
spec.components.response("201", {"description": "Created"})
spec.components.response("202", {"description": "No Content (accepted)"})
spec.components.response("204", {"description": "No Content (success)"})
spec.components.response("302", {"description": "Found"})
spec.components.response("400", _error("Bad Request", ex.API_400, "ErrorBadRequest"))
spec.components.response("401", _error("Unauthorized", ex.API_401, "Error"))
spec.components.response("404", _error("Not Found", ex.API_404, "Error"))
spec.components.response("Ping", _200_ok(ex.API_PING, "Ping"))
spec.components.response("Index", _200_ok(ex.API_INDEX))
spec.components.response("BenchmarkEntity", _200_ok(ex.BENCHMARK_ENTITY))
spec.components.response("BenchmarkList", _200_ok([ex.BENCHMARK_ENTITY]))
spec.components.response("BenchmarkCreated", _201_created(ex.BENCHMARK_ENTITY))
spec.components.response("CommitEntity", _200_ok(ex.COMMIT_ENTITY))
spec.components.response("CommitList", _200_ok([ex.COMMIT_ENTITY]))
spec.components.response("CompareEntity", _200_ok(ex.COMPARE_ENTITY))
spec.components.response("CompareList", _200_ok(ex.COMPARE_LIST))
spec.components.response("ContextEntity", _200_ok(ex.CONTEXT_ENTITY))
spec.components.response("ContextList", _200_ok([ex.CONTEXT_ENTITY]))
spec.components.response("HistoryList", _200_ok([ex.HISTORY_ENTITY]))
spec.components.response("MachineEntity", _200_ok(ex.MACHINE_ENTITY))
spec.components.response("MachineList", _200_ok([ex.MACHINE_ENTITY]))
spec.components.response("RunEntity", _200_ok(ex.RUN_ENTITY))
spec.components.response("RunList", _200_ok(ex.RUN_LIST))
spec.components.response("UserEntity", _200_ok(ex.USER_ENTITY))
spec.components.response("UserList", _200_ok(ex.USER_LIST))
spec.components.response("UserCreated", _201_created(ex.USER_ENTITY))


tags = [
    {"name": "Authentication"},
    {"name": "Index", "description": "List of endpoints"},
    {"name": "Users", "description": "Manage users"},
    {"name": "Benchmarks", "description": "Record benchmarks"},
    {"name": "Commits", "description": "Benchmarked commits"},
    {"name": "Comparisons", "description": "Benchmark comparisons"},
    {"name": "Contexts", "description": "Benchmark contexts"},
    {"name": "History", "description": "Benchmark history"},
    {"name": "Machines", "description": "Benchmark machines"},
    {"name": "Runs", "description": "Benchmark runs"},
    {"name": "Ping", "description": "Monitor status"},
]

for tag in tags:
    spec.tag(tag)
