# Legacy Python Reference

This reference is the detailed catalog behind the
[Python app migration guide](python-app.md). It is for teams that need to map a
specific Flask route, Python package, or old workflow to its new Conbench path.

The new system is not a source-compatible Python port. It is a cleaner Conbench
with a Go server, Svelte dashboard, CLI-first writes, generated SDKs, and a
documented migration path.

Start with the [migration guide](python-app.md) if you want the shortest path
to cut over a benchmark job.

## What Changes

| Old surface | New surface |
| --- | --- |
| Flask API and Jinja dashboard | Go API and Svelte dashboard |
| Password/session Python HTTP clients | Generated SDKs for reads; API tokens for automation |
| `benchconnect submit` and direct POST helpers | `conbench results submit` |
| `benchalerts` PR checks/comments | `conbench ci report` and CI step summaries |
| `/api/history/download/{id}/` CSV downloads | `conbench history export <result-id>` |
| Legacy run lifecycle helpers | explicit `run_id`, `run_tags`, `batch_id`, and CI report selectors |
| Old Sphinx/autodoc docs | this Markdown/Zensical docs site |

The Postgres schema remains frozen during the rewrite so existing data can be
read by the new server. API names, client package names, and workflow contracts
are allowed to improve.

For a shorter product-status view of what was replaced, intentionally retired,
or left as future product work, read the [legacy parity roadmap](legacy-parity-roadmap.md).

## Dashboard Route Crosswalk

Some legacy Flask/Jinja workflows are replaced by dashboard pages. Others are
API, CLI, or SDK workflows because the new product exposes the underlying job
in a different place instead of preserving the old route shape.

| Legacy route or workflow | New path today | Dashboard parity |
| --- | --- | --- |
| `/`, `/index/` recent run landing page | `/` recent-run dashboard, with run detail and CI diagnostics links | Implemented |
| `/benchmark-results/{id}/`, `/benchmarks/{id}/` | `/results/{id}` or `/benchmark-results/{id}` | Implemented, including raw metadata, history JSON export, and signed-in distribution-change/delete actions |
| `/benchmark-results/` result list | `/results`, `/api/benchmark-results?...`, generated SDK, and run/batch dashboards | Implemented as a bounded, filterable result-list dashboard plus API/SDK access |
| `/c-benchmarks/*`, series browsing, and history discovery | `/series`, `/series?q=<benchmark-name>`, `/benchmarks/history/{id}`, and `/series/{fingerprint}` | Implemented as bounded series discovery, loaded benchmark-family drilldown, and per-series investigation; the old global BMRT slope-ranking page is retired |
| `/api/history/download/{id}/` | `conbench history export <result-id>`; result pages link to history JSON | CSV export is CLI-owned; dashboard exposes JSON history |
| `/compare/benchmark-results/{ids}/` | `/compare?baseline=<id>&contender=<id>` | Implemented with stricter same-fingerprint semantics |
| `/compare/runs/{ids}/` | `/ci/report?run_ids=...&baseline_run_ids=...` | Implemented replacement surface |
| `/runs/{id}/` | `/runs/<run_id>` | Implemented as new dashboard surface, not a Flask-compatible alias |
| `/api/runs/{id}/` | `/api/benchmark-results?run_id=...`; `conbench ci report --run-ids ...` | API/CLI first; legacy API route retired |
| `/batches/{id}/` | `/batches/<batch_id>` and `/api/benchmark-results?batch_id=...` | Implemented as new dashboard surface, not a Flask-compatible alias |
| `/hardware/*`, `/api/hardware/*` | series hardware filter and embedded hardware metadata | Retired as standalone catalog |
| `/users/*`, `/register/`, password login | OIDC, `/account`, `/api/users/me`, `/api/tokens`, `conbench auth ...` | Password-era admin UI retired; self-service identity, tokens, and alert rules live on `/account` |

If a row says API/CLI first, the replacement is supported for migration, but the
new dashboard may expose the workflow through a more specific page instead of a
Flask-compatible list or catalog. Route aliases are intentionally not
compatibility contracts.

## Migration Checklist

1. Identify where benchmark results are constructed.
2. Ensure each result payload has the metadata needed by the new workflows.
3. Write one JSON object per result file.
4. Replace Python HTTP submission with `conbench results submit`.
5. Replace client-side alerting or PR comments with `conbench ci report`.
6. Move read automation to the generated Python SDK or direct API calls.
7. Remove password-login client code and legacy Flask route assumptions.
8. Remove old package imports once the JSON/CLI path is in place.

## Package Names And Environments

The new generated Python SDK is installed and imported as `conbench`:

```bash
python -m pip install conbench
```

From a source checkout:

```bash
python -m pip install ./sdk/python
```

Use a clean virtual environment for the new SDK. Do not install the retired
Flask application package and the new generated SDK into the same environment;
they both use the `conbench` import name for different purposes.

```python
from conbench import Client
from conbench.api.default import list_series
```

There is no new `conbench_client` package. The old Flask application also used
the `conbench` import name, so avoid mixed environments where the retired app
package and the new SDK are installed together. In most benchmark CI jobs, the
simplest migration is to avoid importing the SDK entirely: write payload JSON
from Python and call the Go `conbench` CLI for submission and CI reporting.

Use the generated SDK for read automation, scripts, and notebooks that need to
query Conbench. Use the CLI for writes.

## Replacing Result API Aliases

Legacy `/api/benchmarks` routes were aliases for benchmark result collection and
detail operations. The new system keeps one result API shape and does not carry
the aliases forward:

| Old route | New path |
| --- | --- |
| `GET /api/benchmarks/` | `GET /api/benchmark-results` |
| `POST /api/benchmarks/` | `conbench results submit`, or direct `POST /api/results` only for clients that intentionally use the OpenAPI contract |
| `GET /api/benchmarks/{id}/` | `GET /api/benchmark-results/{id}` |
| `PUT /api/benchmarks/{id}/` | authenticated `PUT /api/benchmark-results/{id}` for `change_annotations` updates |
| `DELETE /api/benchmarks/{id}/` | authenticated `DELETE /api/benchmark-results/{id}` |

Prefer the CLI for creating results so validation, glob handling, token
resolution, and CI report integration stay consistent. Use the HTTP update and
delete routes only for authenticated result management workflows.

## Result Payload Metadata

For CI and dashboard workflows, each payload should include:

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

## Recommended Migration Sequence

1. Keep your existing benchmark runner and result-construction code.
2. Add or normalize `run_id`, `run_reason`, `run_tags`, `github.repository`,
   `github.commit`, `timestamp`, and `machine_info`.
3. Write one payload object per JSON file into a directory such as
   `bench-results/`.
4. Run `conbench results submit "bench-results/*.json"` with an API token.
5. Add `conbench ci report` after submission for pull request diagnostics.
6. Move any read-only Python automation to `from conbench import Client`.
7. Delete password-login client code after the CI and read paths have moved.

## Replacing `benchadapt`

`benchadapt` package code is deleted from the maintained implementation. Keep
the payload construction concept, not the import path:

```python
payload = benchmark_result.to_publishable_dict()
```

If existing benchmark code still constructs a similar result object, add or
normalize metadata and write the payload to a JSON file:

```python
payload["run_id"] = run_id
payload["run_reason"] = "pull request"
payload["run_tags"] = {"suite": "gbench"}
payload["github"] = {
    "repository": repository,
    "commit": commit,
}
```

Do not treat `benchadapt` as a long-term compatibility promise. Use the current
`conbench.migration` helper for payload-file writing and CLI invocation. If
real migrations show repeated pain around richer payload construction, any
follow-up should still be narrow and evidence-driven, not a full port of all
historical adapters.

## Replacing `benchconnect`

`benchconnect` and `benchclients` are deleted from the maintained
implementation. Do not build new code around their imports or CLIs; use the
supported `conbench` binary and generated SDK instead.

Old surfaces:

```text
benchconnect submit benchmark-results.json
benchconnect.post(...)
benchconnect.put(...)
```

New create/submit shape:

```bash
conbench results submit "bench-results/*.json" \
  --server "$CONBENCH_SERVER_URL"
```

Set `CONBENCH_TOKEN` in the job environment for authenticated submissions. The
CLI reads that token directly, so migration scripts do not need to put it on
the command line.

Important differences:

- the glob should be quoted so the CLI expands it consistently,
- each matched file must contain one result object,
- auth uses user-owned API tokens, not password-login sessions,
- run grouping is explicit through `run_id`, `run_tags`, and `batch_id`,
- submit output is line-oriented and reports each accepted or rejected file.

Old `benchconnect post` workflows should become the same CLI submit path unless
they intentionally need to call the OpenAPI `POST /api/results` endpoint
directly. Old `benchconnect put` workflows should become authenticated
`PUT /api/benchmark-results/{id}` calls and should only update
`change_annotations`; they are not a general result rewrite path.

There is no replacement for `benchconnect start run` or `benchconnect finish
run`. Generate a stable `run_id`, optional `batch_id`, and shared `run_tags` at
the start of the benchmark job, attach them to every result payload, and submit
the files when the job finishes:

```python
run_id = f"gbench-{github_run_id}-{github_run_attempt}"
run_tags = {"suite": "gbench", "source": "github-actions"}

for payload in payloads:
    payload["run_id"] = run_id
    payload["batch_id"] = batch_id
    payload["run_tags"] = run_tags
```

If your current code writes an array of results, split it:

```python
import json

for i, payload in enumerate(payloads):
    path = out_dir / f"result-{i:04d}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
```

## Replacing CSV History Downloads

Old shape:

```bash
curl "$CONBENCH_URL/api/history/download/$RESULT_ID/" > history.csv
```

New shape:

```bash
conbench history export "$RESULT_ID" \
  --server "$CONBENCH_SERVER_URL" \
  --output history.csv
```

For Python automation that wants structured data instead of a CSV file, use the
generated SDK or the JSON history API directly. The CSV command exists for file
export and notebook handoff workflows; it is not a compatibility alias for the
old Flask route.

## Replacing Batch Pages

Old shape:

```text
/batches/<batch_id>/
```

New shape:

```text
/batches/<batch_id>
```

For automation, use the result-list API:

```bash
curl "$CONBENCH_SERVER_URL/api/benchmark-results?batch_id=$BATCH_ID"
```

Or with the generated Python SDK:

```python
from conbench import Client
from conbench.api.default import list_benchmark_results

client = Client(base_url=server_url)
page = list_benchmark_results.sync(client=client, batch_id=batch_id)
```

The new system treats `batch_id` as submitted metadata. The Svelte dashboard
page at `/batches/<batch_id>` uses the result-list API underneath, groups loaded
rows by `run_id`, and links to run detail, CI reports, result detail, and series
trends. It is not a Flask/Jinja page or API compatibility alias.

## Replacing Run Pages And Run APIs

Old shapes:

```text
/api/runs/?commit_hash=<sha>
/api/runs/<run_id>/
/runs/<run_id>/
```

New result-list shape:

```bash
curl "$CONBENCH_SERVER_URL/api/benchmark-results?run_id=$RUN_ID"
```

Or with the generated Python SDK:

```python
from conbench import Client
from conbench.api.default import list_benchmark_results

client = Client(base_url=server_url)
page = list_benchmark_results.sync(client=client, run_id=run_id)
```

The old run detail endpoint returned a representative result plus run metadata
and candidate baseline suggestions. The new system keeps `run_id`, `run_tags`,
`run_reason`, commit metadata, machine metadata, timestamps, and result status
on the result rows themselves, then uses CI reports for baseline diagnostics.

The new dashboard home page is powered by a recent-run summary endpoint:

```bash
curl "$CONBENCH_SERVER_URL/api/runs/recent?page_size=25"
```

Use it for landing-page activity summaries. For human investigation, open the
new dashboard run detail page:

```text
/runs/<run_id>
```

The dashboard page uses the result-list API underneath and adds links to CI
reports, result details, and series trends. It is not a replacement for the old
`/api/runs/<run_id>/` JSON shape; API migrations should use the result-list
filter and CI report selectors below.

For a known run:

```bash
conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --run-ids "$RUN_ID" \
  --format markdown
```

For a commit-wide replacement of `/api/runs/?commit_hash=...`, ask the CI report
selector to find the commit's runs:

```bash
conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --repository "$REPOSITORY" \
  --commit "$COMMIT_SHA" \
  --format markdown
```

The old `/api/runs` route shapes are retired rather than kept as aliases. If a
migration needs a concise run summary, build it from
`/api/benchmark-results?run_id=...`; if it needs baseline selection, use
`/api/ci/report` or `conbench ci report`.

## Replacing Low-Level Object Catalogs

Old shapes:

```text
/api/commits/
/api/contexts/
/api/hardware/
/api/info/
/hardware/
/hardware/<hardware-id>/
```

The new system does not keep standalone catalog endpoints for these internal
rows. Query the product endpoint that owns the workflow:

- result detail for raw commit, context, info, optional info, validation,
  annotations, hardware metadata, and authenticated result actions,
- result list, run dashboards, and batch dashboards for run, batch, run reason,
  and time-scoped result inspection,
- series browse or trend pages for hardware/repository/fingerprint navigation,
- CI reports for commit and hardware metadata in regression diagnostics.

For example, to replace a hardware page workflow, search or filter series by
hardware name in the dashboard or API:

```bash
curl "$CONBENCH_SERVER_URL/api/series?hardware=$HARDWARE_NAME"
```

These route shapes are retired, not aliased. If a deployment needs an operator
debug catalog, add it as a new authenticated operator feature with its own
authorization and scale requirements.

## Replacing Conceptual Benchmark Pages

Old shapes:

```text
/c-benchmarks/
/c-benchmarks/<benchmark-name>
/c-benchmarks/<benchmark-name>/trends
/c-benchmarks/<benchmark-name>/<case-id>
```

These Flask/Jinja pages were backed by the old BMRT cache. They grouped a
benchmark family by case, hardware, and context; showed case-parameter value
counts; hid stale case keys; and highlighted increasing and decreasing trend
candidates across many series.

The new supported path is:

- use `/series` to find a benchmark family or narrow by repository, hardware,
  active window, or fingerprint,
- use `/series?q=<benchmark-name>` for the loaded benchmark-family drilldown:
  case variants, hardware/context coverage, history-point counts, and
  regressed/improved triage links over the loaded rows,
- use `/series/<fingerprint>` or `/benchmarks/history/<result-id>` for one
  concrete series trend,
- use run, batch, CI report, and result-detail pages to move from a submitted
  run to the relevant series.

The old global increasing/decreasing trend page is retired. It ranked slopes
from the BMRT cache across a whole benchmark family, which is the wrong shape
for a 100M-row result table. Use the loaded family triage, CI reports, and
per-series outlier/step shortcuts instead. A future server-side family
analytics endpoint can be proposed with explicit scale requirements, but it
should not resurrect the old cache model.

## Replacing User Admin And Registration

Old shapes:

```text
/api/users/
/api/users/<user-id>/
/api/register/
/users/
/users/create/
/users/<user-id>/
/register/
```

The new system uses OIDC for human identity and user-owned API tokens for
automation. It supports the `/account` dashboard, `/api/users/me`,
`/api/auth/*`, `/api/tokens`, and the CLI commands:

```bash
conbench auth login --server "$CONBENCH_SERVER_URL"
conbench auth token list --server "$CONBENCH_SERVER_URL"
conbench auth token revoke <token-id> --server "$CONBENCH_SERVER_URL"
```

The `/account` page is a self-service surface for the current authenticated
user: it shows OIDC identity, supports browser logout, creates and revokes
user-owned API tokens, and manages user-owned alert rules. Password login,
registration keys, arbitrary user create/update/delete APIs, and Flask/Jinja
user admin pages are retired for cutover. If operator user administration is
needed later, build it as a new authenticated admin feature rather than
carrying forward the old password-era CRUD routes.

## Replacing `benchclients`

`benchclients.ConbenchClient` is retired, and the `benchclients/` package code
has been deleted from the maintained implementation. Use:

- the `conbench` CLI for writes and CI reports,
- the generated Python SDK package `conbench` for reads and automation,
- direct OpenAPI calls only when a generated SDK is not appropriate.

Example read automation:

```python
from conbench import Client
from conbench.api.default import get_benchmark_result

client = Client(base_url="https://conbench.example.com")
result = get_benchmark_result.sync(client=client, id=result_id)
```

Do not port password-login, cookie-session, or legacy pagination helpers.
If existing code uses `ConbenchClient.get_all(...)`, replace it with the
generated SDK operation for the endpoint you actually need and follow the
operation's `next_page_cursor` when the response type exposes one.

## Replacing Run Comparison Pages

Old shape:

```text
/compare/runs/<baseline-run-id>...<contender-run-id>/
/api/compare/runs/<baseline-run-id>...<contender-run-id>/
```

New shape:

```bash
conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --run-ids "$CONTENDER_RUN_ID" \
  --baseline-run-ids "$BASELINE_RUN_ID" \
  --format markdown
```

For multiple run pairs, pass comma-separated lists with matching order. The
report URL also accepts `run_ids` and `baseline_run_ids`, so the same comparison
can be opened in the Svelte dashboard. The new system intentionally uses the CI
report surface instead of preserving the old Flask route shape.

## Compare Semantics Change

Legacy Conbench allowed some ad hoc same-unit result comparisons even when the
results came from different benchmark cases, contexts, or repositories. The new
single-result compare is intentionally stricter: it expects baseline and
contender results from the same history fingerprint so pairwise output and
lookback z-score context describe the same benchmark series.

Use CI reports for run-to-run and commit-wide comparisons. If a migration needs
cross-fingerprint exploratory comparison, treat that as a new product feature
with explicit UX and statistics semantics rather than relying on the old loose
route behavior.

## Replacing `benchalerts`

For synchronous pull request checks, use `conbench ci report`:

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

This replaces `benchalerts` for synchronous PR diagnostics: the CI job owns the
GitHub status, and the Markdown report can be appended to the job summary or
posted by repository-local automation.

Scheduled alert state moves into the server. Create alert rules through the
`/account` dashboard or authenticated alert-rule API, then run
`conbench admin alerts evaluate` from operations automation. The evaluator
records open/resolve events using the CI report comparison engine.

```bash
conbench admin alerts evaluate --format json
```

For scheduled notifications, run `conbench admin alerts deliver` with
`CONBENCH_ALERT_WEBHOOK_URL` or `--webhook-url` for a generic webhook. For
Slack, use `--channel slack` with `CONBENCH_ALERT_SLACK_WEBHOOK_URL` or
`--slack-webhook-url`. For repository-scoped scheduled GitHub Checks, use
`--channel github-check` with `CONBENCH_ALERT_GITHUB_REPOSITORY` and a token
that can create Check Runs. For repository-scoped GitHub commit comments, use
`--channel github-comment` with the same repository and token configuration. For
email delivery, use `--channel email` with
`CONBENCH_ALERT_EMAIL_SMTP_ADDR`, `CONBENCH_ALERT_EMAIL_FROM`, and
`CONBENCH_ALERT_EMAIL_TO`. All paths deliver stored alert events through an
idempotent, auditable server-owned outbox rather than through a maintained
`benchalerts` Python client package.

```bash
conbench admin alerts deliver \
  --webhook-url "$CONBENCH_ALERT_WEBHOOK_URL" \
  --format json
```

See [Alerting](../alerting.md) for channel-specific configuration and the
current non-goals.

## Replacing `benchrun` And `conbenchlegacy`

`benchrun` package code is deleted from the maintained implementation.
`conbenchlegacy` package code is deleted from the maintained implementation.
Benchmark orchestration belongs in benchmark projects. The new
`conbench.migration` helper only covers payload-file writing and CLI submission;
it does not carry forward old decorators or runner APIs.

- Keep benchmark execution code that is still useful.
- Emit Conbench JSON payloads at the boundary.
- Submit with the Go CLI.
- Do not keep old decorators or runner APIs just to preserve import paths.

If a real benchmark suite needs more than this helper, capture the specific pain
as a concrete migration requirement before adding another abstraction.

## Optional Python Migration Helper

The new `conbench` Python SDK includes a narrow `conbench.migration` module for
jobs that already build result dictionaries and need a small bridge to the Go
CLI:

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
errors. Before writing, it removes older helper-owned files with the same
prefix, such as `result-000003.json`, so a submit glob does not pick up stale
payloads from a previous run. It is not a source-compatible `benchadapt`,
`benchconnect`, or `benchclients` shim; benchmark projects should still own
their benchmark execution and payload construction.

## Google Benchmark Demo

The repository includes a fixture-backed migration demo,
[`examples/migration/gbench_to_cli_submit.py`](https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py),
that transforms saved Google Benchmark JSON without compiling Google Benchmark:

```bash
make migration-examples-test

PYTHONPATH=sdk/python python3 examples/migration/gbench_to_cli_submit.py \
  --out-dir /tmp/conbench-gbench-payloads \
  --repository https://github.com/example/project \
  --commit abc123 \
  --run-id demo-run
```

To keep this proof honest, the repository check runs the example tests with the
repository root and `sdk/python` on `PYTHONPATH`. The repository root is present
only so tests can import repository guard helpers; the demo itself must not
depend on installed legacy packages or developer-shell state.

The dry run prints the files it wrote and the exact submit command shape. It
does not include the API token on argv:

```json
{
  "files": [
    "/tmp/conbench-gbench-payloads/result-000001.json",
    "/tmp/conbench-gbench-payloads/result-000002.json"
  ],
  "result_count": 2,
  "run_ids": [
    "demo-run"
  ],
  "submit_command": [
    "conbench",
    "results",
    "submit",
    "/tmp/conbench-gbench-payloads/*.json",
    "--server",
    "$CONBENCH_SERVER_URL"
  ],
  "submit_env": {
    "CONBENCH_TOKEN": "<redacted>"
  }
}
```

The test target is part of the CI path and proves that the demo still writes
object-per-file payloads without leaking tokens. The converter preserves the
Google Benchmark `context.date` timestamp when it is present, which keeps
historical imports and dry-run output reproducible. It uses the supported
`conbench.migration` helper for payload-file writing and CLI result submission,
so the runnable example follows the same Python boundary recommended above. Its
dry-run summary shows the submit command without a `--token` argument and lists
`CONBENCH_TOKEN` as redacted environment input, matching the helper's
process-listing-safe token path. The optional `--ci-report` step follows the
same rule: it runs `conbench ci report` with `CONBENCH_TOKEN` in the child
environment rather than on argv.
Submit with:

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
object per file.

## Arrow And Archery Coverage

The Google Benchmark fixture demo is the current executable migration proof
because it exercises the result-construction, metadata-normalization, file
writing, timestamp preservation, CLI submission, and CI-report path without a
heavyweight C++ build.

Arrow/archery remains the representativeness anchor for real Conbench usage. A
richer Arrow/archery example is not required for the first migration path.
Arrow/archery migration does not block initial cutover: the generic JSON/CLI
path is sufficient while the first deployments migrate, and a new
self-contained recipe should be added only if real Arrow migration work shows
archery-specific metadata or adapter behavior that the fixture demo does not
cover.

Legacy adapter status:

| Legacy adapter | Current migration path |
| --- | --- |
| Google Benchmark / `gbench` | Covered by the fixture-backed migration demo. |
| Archery / Arrow | Representativeness anchor; add a self-contained recipe only when real migration work shows archery-specific metadata gaps. |
| Folly | Not source-compatible; emit Conbench payload dictionaries with explicit run, GitHub, timestamp, machine, tags, context, and stats fields. |
| ASV | Not source-compatible; translate ASV output into one Conbench result object per file before CLI submission. |
| Callable adapter | Retired with `benchrun`; keep useful benchmark execution code in the benchmark project and emit Conbench JSON at the boundary. |

## Package-By-Package Outcome

| Package | Outcome | What to do now | What not to carry forward |
| --- | --- | --- | --- |
| `benchadapt` | Deleted from the maintained implementation; replace | Preserve the payload-construction concept if useful; normalize metadata; submit with CLI | A full source-compatible adapter package |
| `benchconnect` | Deleted from the maintained implementation; replace | Use `conbench results submit` and `conbench ci report` | Password/session posting and implicit run lifecycle |
| `benchclients` | Deleted from the maintained implementation; replace | Use generated `conbench` SDK reads and CLI writes | `ConbenchClient`, password login, cookie sessions, legacy pagination helpers |
| `benchrun` | Deleted from the maintained implementation; retire | Keep useful benchmark execution code in the benchmark project; emit Conbench JSON at the boundary | Old decorators or runner APIs solely to preserve imports |
| `benchalerts` | Deleted from the maintained implementation; replace PR checks and scheduled alert state with server-owned surfaces | Use CI reports for PRs; use `/account` or the alert-rule API plus `conbench admin alerts evaluate`; use `conbench admin alerts deliver` for generic webhook, Slack, GitHub Check, GitHub commit-comment, or email notifications | Client-side GitHub Checks, comments, Slack routing, or email routing as a maintained package |
| `conbenchlegacy` | Deleted from the maintained implementation; retire | Migrate benchmark output to JSON payloads plus CLI | Legacy runner/import compatibility |
| Flask `conbench` app | Deleted from the maintained implementation; replace | Deploy Go server and Svelte app | Flask route, Jinja, password-login, and SQLAlchemy app contracts |

## PyPI And Release Communication

Before cutover, publish or otherwise communicate the legacy package status in
the same places users discover the packages today:

- Use the [legacy package deprecation notices](deprecation-notices.md) as
  copy-paste source text for package READMEs, PyPI project descriptions,
  release notes, GitHub issues, and migration pull requests.
- Update package READMEs and PyPI long descriptions with the migration notice.
- Publish final deprecation notices for `benchconnect`, `benchclients`,
  `benchalerts`, and `conbenchlegacy` where those packages are still
  discovered, such as PyPI project pages or old docs.
- In the `benchalerts` deprecation notice, point synchronous PR checks to
  `conbench ci report`, scheduled alert state to server alert rules, generic
  webhook, Slack, GitHub Check, GitHub commit-comment, and email delivery to
  `conbench admin alerts deliver`; do not promise a maintained Python alerting
  client or package-level delivery shim.
- Point old `benchadapt` users at the self-contained migration examples and at
  `conbench.migration`; do not promise import compatibility.
- Make the generated SDK package `conbench` the supported Python read client.
- Warn that the old Flask app package and the new SDK both use the `conbench`
  import name and should not share an environment.
- Warn that `conbenchlegacy` exposes a `conbench` console script that conflicts
  conceptually with the new Go CLI; migration jobs should call the Go binary.
- Link release notes, GitHub Pages, package READMEs, and pull request
  announcements to this guide and the parity roadmap.
- Do not remove old package distributions from package indexes unless there is a
  security or legal reason; users need time to pin and migrate.

Any compatibility shim, import alias, or replacement helper beyond the generated
SDK, `conbench.migration`, and Go CLI needs explicit approval before
implementation.

## Cutover Expectations

During migration, users may still have old packages in their own benchmark
environments. Those packages are no longer maintained source surfaces. At
cutover, users should expect:

- no maintained Flask application,
- no maintained password-login Python HTTP client,
- no source-compatible `benchconnect` or `benchalerts` replacement,
- new documentation, CLI, OpenAPI, and SDKs as the supported path.

The goal is a smaller, clearer Conbench that existing deployments can migrate
to without carrying old design constraints forever.
