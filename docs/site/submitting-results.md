# Submitting Results

The supported write path is:

1. benchmark code emits Conbench-compatible JSON payload files,
2. each file contains either one result object or an array of result objects,
3. the Go `conbench` CLI submits those files with bounded concurrency.

```bash
conbench results submit "bench-results/*.json" \
  --server "$CONBENCH_SERVER_URL" \
  --jobs 16
```

If `CONBENCH_TOKEN` is set, no `--token` flag is needed. Prefer the environment
variable in CI and shared scripts; use `--token` only when you need an explicit
local override.

## Required Shape

At minimum, a measured result needs tags, context, commit context, run identity,
a timestamp, hardware metadata, and stats:

```json
{
  "tags": {"name": "ReadParquet/rows=1000000"},
  "context": {"benchmark_language": "C++"},
  "github": {
    "repository": "https://github.com/org/project",
    "commit": "abcdef123"
  },
  "run_id": "gbench-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}",
  "run_reason": "pull request",
  "run_tags": {"suite": "gbench", "source": "github-actions"},
  "timestamp": "2026-06-17T12:00:00Z",
  "machine_info": {"name": "ci-linux-x86-64"},
  "stats": {"unit": "s", "data": [1.24, 1.21, 1.22]}
}
```

Useful production payloads should also include:

- rich `tags`: benchmark dimensions that define the time series,
- rich `context`: toolchain, language, runtime, and other comparison context,
- `run_reason`: `pull request`, `nightly`, `manual`, or similar,
- `run_tags`: CI system, suite, shard, language, benchmark family,
- `batch_id`: optional grouping across related runs,
- `github.repository` and `github.commit`: required for commit-wide CI reports,
- `github.pr_number` or `github.branch`: useful for display and audit.

## Multi-Result Submission

Object-per-file output is still a good default:

```text
bench-results/
  result-0001.json
  result-0002.json
  result-0003.json
```

Array files are also accepted, which is useful for benchmark harnesses that
already produce one JSON document containing many cases. When more than one
result is submitted, stdout is JSON Lines with per-result success or error
state; array entries include an `index` field. Use `--jobs` to control the
maximum number of concurrent HTTP submissions. The default is suitable for small
CI jobs; larger benchmark suites should set it explicitly after measuring their
server and database capacity.

## Existing Python Result Builders

Existing Python code can keep using local helpers or existing result objects to
construct payload dictionaries during migration. The supported change is to
replace the old post step with the Go CLI:

```python
payload = result.to_publishable_dict()
payload["run_id"] = run_id
payload["github"] = {
    "repository": repository,
    "commit": commit,
}
```

Then write `payload` as JSON and submit with the CLI. Do not port password-login
HTTP submission code into new benchmark suites.

For package-by-package migration guidance, read the
[Python app migration guide](migration/python-app.md). For a runnable migration
example, see
[`examples/migration/gbench_to_cli_submit.py`](https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py).
It transforms a saved Google Benchmark JSON fixture into Conbench payloads,
fills run and GitHub metadata, uses `conbench.migration` for
payload-file writing and CLI submission, preserves the fixture timestamp when
Google Benchmark provides one, redacts tokens from dry-run output, prints the
dry-run submit command without a `--token` argument, and can optionally call
`conbench results submit` followed by `conbench ci report`. Both subprocesses
receive the API token through `CONBENCH_TOKEN`, not an argv flag.

From a source checkout, run the example with the SDK source on `PYTHONPATH`:

```bash
PYTHONPATH=sdk/python python3 examples/migration/gbench_to_cli_submit.py \
  --out-dir /tmp/conbench-gbench-payloads \
  --repository https://github.com/example/project \
  --commit abc123 \
  --run-id demo-run
```
