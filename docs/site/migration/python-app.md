# Migrating From The Legacy Python Conbench App

This guide is for teams moving off the retired Python/Flask Conbench app and
old Python client packages.

The new system is not a source-compatible Python port. It is a smaller Conbench
with a Go server, Svelte dashboard, CLI-first writes, generated SDKs for reads,
and a frozen-schema migration path for existing data.

If you need route-by-route or package-by-package details, keep this page open
and use the [legacy Python reference](python-legacy-reference.md) as the
catalog.

## Short Version

Use this path for most benchmark jobs:

1. Keep the benchmark runner that still produces useful measurements.
2. Emit one Conbench result JSON object per file.
3. Include explicit `run_id`, `run_tags`, `github.repository`,
   `github.commit`, `timestamp`, and `machine_info`.
4. Submit those files with `conbench results submit`.
5. Add `conbench ci report` after submission for pull request diagnostics.
6. Use the generated Python SDK only for read/query automation.
7. Remove legacy imports and password-login client code after the CLI path is
   working.

## What Changes

| Old surface | New surface |
| --- | --- |
| Flask API and Jinja dashboard | Go API and Svelte dashboard |
| Password/session Python HTTP clients | Generated SDKs for reads; API tokens for automation |
| `benchconnect submit` and direct POST helpers | `conbench results submit` |
| `benchalerts` PR checks/comments | `conbench ci report` with `--github-check` and `--github-pr-comment` when repository-facing GitHub output is required |
| `/api/history/download/{id}/` CSV downloads | `conbench history export <result-id>` |
| Legacy run lifecycle helpers | explicit `run_id`, `run_tags`, `batch_id`, and CI report selectors |
| Old Sphinx/autodoc docs | this Markdown/Zensical docs site |

The Postgres schema remains frozen during the rewrite so existing data can be
read by the new server. API names, client package names, and workflow contracts
are allowed to improve.

For a product-status view of what was replaced, retired, or left as future
product work, read the [legacy parity roadmap](legacy-parity-roadmap.md). For
the full route crosswalk, read the
[legacy Python reference](python-legacy-reference.md#dashboard-route-crosswalk).

## Package Names And Environments

The new generated Python SDK installs and imports as `conbench`:

```bash
python -m pip install conbench
```

From a source checkout:

```bash
python -m pip install ./sdk/python
```

There is no new `conbench_client` package. Do not install the retired Flask app
package and the new generated SDK into the same environment; both use the
`conbench` import name for different purposes.

Use the generated SDK for read automation:

```python
from conbench import Client
from conbench.api.default import list_series
```

For most benchmark CI jobs, do not import the SDK at all. Write result JSON from
Python and call the Go `conbench` CLI for submission and CI reporting.

## Result Payload Minimum

Each payload should include enough metadata for CI reports and dashboard
navigation:

```json
{
  "tags": {
    "name": "example-benchmark"
  },
  "run_id": "suite-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}",
  "run_reason": "pull request",
  "run_tags": {
    "suite": "cpp",
    "source": "github-actions"
  },
  "context": {
    "benchmark_language": "Python"
  },
  "github": {
    "repository": "https://github.com/org/project",
    "commit": "abcdef123"
  },
  "timestamp": "2026-06-17T12:00:00Z",
  "machine_info": {
    "name": "ci-linux-x86-64"
  },
  "stats": {
    "unit": "ns",
    "data": [101.0, 99.5, 100.2]
  }
}
```

The `github.commit` value must match the commit passed to
`conbench ci report --commit`. This is the most common migration failure.

## Submit Results

Write one payload object per JSON file, then submit a quoted glob:

```bash
export CONBENCH_SERVER_URL=https://conbench.example.com
export CONBENCH_TOKEN=<token>

conbench results submit "bench-results/*.json" \
  --server "$CONBENCH_SERVER_URL"
```

The CLI reads `CONBENCH_TOKEN` from the environment, so migration scripts do not
need to put tokens on the command line.

If your current code writes an array of results, split it before submitting:

```python
import json

for i, payload in enumerate(payloads):
    path = out_dir / f"result-{i:04d}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
```

## Add CI Reporting

For pull request diagnostics, run `conbench ci report` after submission:

```bash
set +e
conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --repository "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}" \
  --commit "$GITHUB_SHA" \
  --run-ids "$RUN_IDS" \
  --format markdown \
  --output conbench-report.md
status=$?
set -e

cat conbench-report.md >> "$GITHUB_STEP_SUMMARY"
exit "$status"
```

This replaces `benchalerts` for synchronous PR diagnostics when a CI job only
needs an exit status and Markdown output.

When the old workflow posted a GitHub App Check Run and pull request comment,
keep that repository-facing behavior by enabling GitHub publishing:

```bash
export CONBENCH_CI_GITHUB_APP_ID="<github-app-id>"
export CONBENCH_CI_GITHUB_APP_PRIVATE_KEY="$(cat /path/to/private-key.pem)"

conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --repository "https://github.com/org/project" \
  --commit "$CI_COMMIT_SHA" \
  --run-ids "$RUN_IDS" \
  --github-check \
  --github-pr-comment \
  --github-pr-number "$CI_PULL_REQUEST_NUMBER" \
  --github-external-id "$CI_BUILD_ID" \
  --build-url "$CI_BUILD_URL"
```

The GitHub App path is runner-agnostic; Buildkite and other external CI systems
should pass their own commit, pull request number, build ID, and build URL.

For scheduled alerting, use server alert rules plus
`conbench admin alerts evaluate` and `conbench admin alerts deliver`. See
[Alerting](../alerting.md).

## Read Automation

Use the generated SDK for reads and scripts that query Conbench:

```python
from conbench import Client
from conbench.api.default import get_benchmark_result

client = Client(base_url="https://conbench.example.com")
result = get_benchmark_result.sync(client=client, id=result_id)
```

Use the CLI for writes. Use direct OpenAPI calls only when a generated SDK is
not appropriate.

## Package-By-Package Outcome

| Package | Outcome | What to do now |
| --- | --- | --- |
| `benchadapt` | Deleted from the maintained implementation | Preserve useful payload-construction concepts; emit Conbench JSON with explicit metadata. |
| `benchconnect` | Deleted from the maintained implementation | Use `conbench results submit` and `conbench ci report`. |
| `benchclients` | Deleted from the maintained implementation | Use generated `conbench` SDK reads and CLI writes. |
| `benchrun` | Deleted from the maintained implementation | Keep benchmark execution code in benchmark projects; emit JSON at the boundary. |
| `benchalerts` | Deleted from the maintained implementation | Use CI reports plus optional GitHub Check/PR-comment publishing for PRs, and server-owned alert rules/outbox for scheduled alerts. |
| `conbenchlegacy` | Deleted from the maintained implementation | Migrate benchmark output to JSON payloads plus CLI. |
| Flask `conbench` app | Deleted from the maintained implementation | Deploy the Go server and Svelte dashboard. |

Required migration facts:

- `benchadapt` package code is deleted; do not treat it as a long-term
  compatibility promise.
- `benchconnect` and `benchclients` are deleted; do not build new code around
  their imports or CLIs.
- `benchclients.ConbenchClient` is retired; replace password-login,
  cookie-session, and legacy pagination helpers with generated SDK operations.
- `benchrun` package code is deleted.
- `conbenchlegacy` package code is deleted.

The detailed route, API, and package notes are in the
[legacy Python reference](python-legacy-reference.md#package-by-package-outcome).

## Optional Migration Helper

The new SDK includes a narrow `conbench.migration` helper for jobs that already
build result dictionaries and need a small bridge to the Go CLI:

```python
from conbench.migration import submit_results, write_result_payloads

write_result_payloads(payloads, "bench-results")
submit_results(
    ["bench-results/*.json"],
    server="https://conbench.example.com",
    token=token,
)
```

The helper writes one JSON object per file, passes quoted glob strings through
to the Go CLI, and redacts tokens from helper-returned command results and
errors. It is not a source-compatible `benchadapt`, `benchconnect`, or
`benchclients` shim.

## Runnable Example

The repository includes a fixture-backed migration demo,
[`examples/migration/gbench_to_cli_submit.py`](https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py),
that converts saved Google Benchmark JSON into object-per-file Conbench
payloads:

```bash
make migration-examples-test

PYTHONPATH=sdk/python python3 examples/migration/gbench_to_cli_submit.py \
  --out-dir /tmp/conbench-gbench-payloads \
  --repository https://github.com/example/project \
  --commit abc123 \
  --run-id demo-run
```

The repository check runs the example tests with the repository root and
`sdk/python` on `PYTHONPATH`. The repository root is present only so tests can
import repository guard helpers; the demo itself must not depend on installed
legacy packages or developer-shell state.

Submit through the same CLI boundary. `--submit` requires the server URL and an
API token; the example reads both from the environment:

```bash
export CONBENCH_SERVER_URL=https://conbench.example.com
export CONBENCH_TOKEN=<token>

PYTHONPATH=sdk/python python3 examples/migration/gbench_to_cli_submit.py \
  --out-dir /tmp/conbench-gbench-payloads \
  --repository "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}" \
  --commit "$GITHUB_SHA" \
  --run-id "gbench-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" \
  --submit \
  --ci-report
```

The demo redacts tokens, preserves fixture timestamps, and writes one result
object per file. Arrow/archery remains the representativeness anchor for real
Conbench usage, but a richer Arrow recipe should be added only if a real
migration exposes archery-specific metadata gaps.

## Cutover Expectations

During migration, users may still have old packages in their own benchmark
environments. Those packages are no longer maintained source surfaces. At
cutover, users should expect:

- no maintained Flask application,
- no maintained password-login Python HTTP client,
- no source-compatible `benchconnect` or `benchalerts` replacement,
- new documentation, CLI, OpenAPI, and SDKs as the supported path.

Any compatibility shim, import alias, or replacement helper beyond the
generated SDK, `conbench.migration`, and Go CLI needs explicit approval before
implementation.

The goal is a smaller, clearer Conbench that existing deployments can migrate
to without carrying old design constraints forever.

## More Detail

- [Legacy Python reference](python-legacy-reference.md) covers old routes,
  aliases, run/batch APIs, conceptual benchmark pages, user administration,
  compare semantics, alert delivery, adapter status, and release communication.
- [Legacy parity roadmap](legacy-parity-roadmap.md) records what is replaced,
  retired, or future product work.
- [Legacy package deprecation notices](deprecation-notices.md) provide
  copy-paste notice text for package READMEs, PyPI pages, release notes, and
  migration pull requests.
