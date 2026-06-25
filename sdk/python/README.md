# conbench Python SDK

Generated Python SDK for the Conbench API.

Install and import this package as `conbench`:

```bash
python -m pip install conbench
```

From a source checkout:

```bash
python -m pip install ./sdk/python
```

Use a clean environment for this SDK. Do not install the retired Flask
application package and the new generated SDK together; they use the same
`conbench` import name for different purposes.

```python
from conbench import Client
from conbench.api.default import list_series

client = Client(base_url="https://conbench.example")
response = list_series.sync_detailed(client=client)
```

This package is generated from `api/openapi.yaml` and is intended for API
reads, dashboard automation, notebooks, and operator scripts. Use the Go
`conbench` CLI for writes, result submission, login, token management, and CI
reports:

```bash
export CONBENCH_TOKEN=<token>

conbench results submit "bench-results/*.json" \
  --server "$CONBENCH_SERVER_URL"

conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --repository "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY" \
  --commit "$GITHUB_SHA" \
  --run-ids "$RUN_IDS" \
  --format markdown
```

Keeping writes in the CLI gives every language the same submission contract and
avoids reintroducing legacy password/session clients. CI jobs should pass the
API token through `CONBENCH_TOKEN`; reserve `--token` for explicit local
overrides.

## Migration from the retired Python/Flask application

The retired Flask application and old Python packages are not source-compatible
with this SDK. Existing benchmark jobs should keep their benchmark execution
code, write Conbench JSON payloads, submit those files with the Go CLI, and use
this SDK only where Python code needs to read API data.

For Python jobs that need a small amount of migration glue, use
`conbench.migration` to write payload files and invoke the Go CLI:

```python
from conbench.migration import submit_results, write_result_payloads

payloads = [
    {
        "run_id": "example-run",
        "github": {
            "repository": "https://github.com/example/project",
            "commit": "abc123",
        },
        "stats": {"data": [1.0], "unit": "ns"},
        "tags": {"name": "example-benchmark"},
    }
]

write_result_payloads(payloads, "bench-results")
submit_results(
    ["bench-results/*.json"],
    server="https://conbench.example",
    token="<api token>",
    jobs=16,
)
```

The helper does not replace `benchadapt` or `benchconnect`; it only keeps the
JSON-file and CLI submission boundary easy to adopt from Python. Each call
removes older helper-owned files with the same prefix, such as
`result-000003.json`, before writing the current payload set so a later
`bench-results/*.json` submit glob does not resend stale results.

Migration documentation:

- Full guide:
  https://conbench.github.io/conbench/migration/python-app/
- Deprecation notice text:
  https://conbench.github.io/conbench/migration/deprecation-notices/
- Parity roadmap:
  https://conbench.github.io/conbench/migration/legacy-parity-roadmap/

The source repository also includes
[`examples/migration/gbench_to_cli_submit.py`](https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py)
for a fixture-backed migration example that preserves fixture timestamps, writes
payload files, and calls the CLI. `make migration-examples-test` verifies that
example.

Do not edit generated modules under `conbench/` by hand. The hand-written
`conbench.migration` source lives in `sdk/python/overlays/conbench/` and is
copied into the package after OpenAPI generation.
