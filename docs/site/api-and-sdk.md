# API And SDK

The Go server publishes OpenAPI from the same huma routes that serve requests.
Generated clients are artifacts of that contract.

## API Discovery

On a running server:

- `/docs` opens interactive API documentation,
- `/openapi.yaml` returns the canonical OpenAPI 3.1 document,
- `/openapi-3.0.yaml` returns the compatibility document used by the Go client
  generator.

## Python SDK

The generated Python SDK distribution and import package are both `conbench`:

```bash
python -m pip install conbench
```

From a source checkout, install the package from `sdk/python` into a clean
environment:

```bash
python -m pip install ./sdk/python
```

```python
from conbench import Client
from conbench.api.default import list_series

client = Client(base_url="https://conbench.example.com")
page = list_series.sync(client=client, page_size=10)
```

List operations expose the same filters as the HTTP API. For example, use the
result-list operation to inspect benchmark results for one batch:

```python
from conbench.api.default import list_benchmark_results

page = list_benchmark_results.sync(client=client, batch_id=batch_id)
```

The SDK is intended for reads and automation. Writes should use the Go CLI so
payload validation, token handling, glob behavior, and CI-report integration
stay consistent.

For jobs that already construct Python dictionaries, the SDK also ships a small
hand-written `conbench.migration` helper. It writes object-per-file payload JSON
and invokes the Go CLI without exposing tokens in helper-returned errors:

```python
from conbench.migration import submit_results, write_result_payloads

files = write_result_payloads(payloads, "bench-results")
submit_results(
    ["bench-results/*.json"],
    server="https://conbench.example.com",
    token=token,
)
```

Each call removes older helper-owned files with the same prefix before writing
the current payload set, which prevents a later `bench-results/*.json` submit
glob from resending stale results.

## Low-Level Objects

Commit, context, hardware, and info rows are exposed through the product
responses that use them:

- result detail responses include commit, context, info, optional info,
  validation, change annotations, hardware data, and raw measurement arrays,
- result-list responses can be filtered by run, batch, run reason, and time,
- series browse and trend responses expose hardware, repository, commit, and
  history identity needed for product workflows,
- CI reports expose commit and hardware metadata alongside comparisons.

For automation, query the product endpoint that owns the workflow instead of
joining low-level object catalogs client-side.

## Alert APIs

The alert-rule APIs are generated into every SDK from OpenAPI, but they require a
user principal: a browser session or user-owned API token. The static operator
token is not a user and cannot manage rules.

Use the SDK for rule management and event inspection when needed. Evaluation is
an operations concern and runs through `conbench admin alerts evaluate`, not
through the SDK.

## Go And TypeScript Clients

The repository also generates:

- a Go client under `sdk/go/conbench`,
- TypeScript API types under `web/src/lib/api`.

Regenerate all clients with:

```bash
make codegen
```

Verify generated artifacts are clean with:

```bash
make codegen-check
```

## Migration Notes

For package-by-package migration guidance, read the
[Python app migration guide](migration/python-app.md). For a runnable example
that converts saved Google Benchmark JSON into CLI-submitted payload files, see
[`examples/migration/gbench_to_cli_submit.py`](https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py).

Migration reference pages:

- [Python app migration guide](migration/python-app.md)
- [legacy package deprecation notices](migration/deprecation-notices.md)
- [legacy parity roadmap](migration/legacy-parity-roadmap.md)

The generated Python SDK distribution and import package are named `conbench`.
During a Python-app migration, do not install the retired Flask application
package and the new generated SDK into the same Python environment, because both
use that import name for different purposes. There is no supported
`conbench_client` import. Benchmark jobs that only submit results do not need
the Python SDK at all; they can emit JSON files and call the Go CLI.

The `conbench.migration` helper is intentionally not a source-compatible
`benchadapt` or `benchconnect` replacement. It keeps the JSON-file and CLI
boundary explicit.
