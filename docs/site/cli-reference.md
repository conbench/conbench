# CLI Reference

The `conbench` binary is the supported command-line surface for writes,
interactive login, CI diagnostics, and trusted operations jobs. The CLI uses
Cobra, so every command supports `--help`:

```bash
conbench --help
conbench results submit --help
conbench ci report --help
```

This page is a map of the maintained command groups. The command-specific
`--help` output is the exact flag reference.

## Result Commands

Submit one or more benchmark result JSON files:

```bash
conbench results submit <file-or-glob>... --server URL
```

Keep globs quoted:

```bash
conbench results submit "bench-results/*.json" --server "$CONBENCH_SERVER_URL" --jobs 16
```

The CLI expands globs internally, validates payloads, resolves credentials, and
submits multiple results with bounded concurrency. Each matched file may contain
one result object or an array of result objects. With exactly one result it
prints one compact JSON result identity. With multiple results it prints one
JSON line per result, including file, optional array index, and success or error
state. Use `--jobs` to tune concurrency for large benchmark suites.

Fetch one result as JSON:

```bash
conbench results get <id> --server URL
```

Use [Submitting Results](submitting-results.md) for payload shape and migration
examples.

## Read And Compare Commands

Compare two benchmark results:

```bash
conbench compare <baseline-id> <contender-id> --server URL
```

List benchmark series:

```bash
conbench series list --server URL
```

Export history CSV for one result's series:

```bash
conbench history export <result-id> --server URL --output history.csv
```

Use [Browsing And Comparing](browsing-and-comparing.md) for the dashboard and
API workflows these commands support.

## CI Commands

Render a CI benchmark report:

```bash
conbench ci report --server URL --repository REPO --commit SHA
```

Common selector forms:

```bash
conbench ci report --server URL --repository REPO --commit SHA --run-ids RUN_IDS
conbench ci report --server URL --run-ids CONTENDER_IDS --baseline-run-ids BASELINE_IDS
```

Publish repository-facing GitHub output from any CI runner:

```bash
conbench ci report \
  --server URL \
  --repository REPO \
  --commit SHA \
  --github-check \
  --github-pr-comment \
  --github-pr-number PR_NUMBER \
  --build-url BUILD_URL
```

`--format json` is the default. Use `--format markdown --output
conbench-report.md` for CI step summaries. Report exit codes are:

| Exit code | Meaning |
| --- | --- |
| `0` | `success` or `skipped` report |
| `1` | `failure` or `action_required` report |
| `2` | usage, authentication, server, transport, or decode error |

Use [CI Reporting](ci-reporting.md) for the metadata contract, GitHub Actions
fragment, GitHub App publishing, baseline modes, and status precedence.

## Authentication Commands

Run browser loopback login and store a user-owned API token:

```bash
conbench auth login --server URL
```

List and revoke API tokens:

```bash
conbench auth token list --server URL
conbench auth token revoke <token-id> --server URL
```

For automation, prefer `CONBENCH_TOKEN` over `--token` so the token is not
placed on process arguments. Explicit `--token` remains available for local
overrides. Credential resolution is:

1. `--token`
2. `CONBENCH_TOKEN`
3. the credentials file written by `conbench auth login`

Use [Authentication And Tokens](auth-and-tokens.md) for browser sessions,
operator tokens, and user-owned API tokens.

## Operations Commands

Repair unknown commit rows after GitHub metadata becomes available:

```bash
conbench admin repair-commits --format json
```

Evaluate server-side alert rules:

```bash
conbench admin alerts evaluate --format json
```

Deliver queued alert events:

```bash
conbench admin alerts deliver --channel webhook --format json
conbench admin alerts deliver --channel slack --format json
conbench admin alerts deliver --channel github-check --format json
conbench admin alerts deliver --channel github-comment --format json
conbench admin alerts deliver --channel email --format json
```

Run the production-clone compatibility harness:

```bash
conbench admin prod-clone --help
conbench admin prod-clone samples --help
```

Use [Operations](operations.md), [Alerting](alerting.md), and
[Production-Clone Compatibility](prod-clone-compatibility.md) for the required
environment variables and safety boundaries.

## API And Server Commands

Emit the OpenAPI document:

```bash
conbench openapi
conbench openapi --downgrade
```

Run the server and embedded Svelte dashboard:

```bash
conbench serve
```

Use [API And SDK](api-and-sdk.md) for generated clients and
[Operations](operations.md) for the runtime environment contract.
