# Temporary Production-Clone Migration Gate

Use this temporary migration gate with a production-derived Postgres clone to
prove that the Go server, Svelte dashboard, CLI, and generated SDK can read an
existing Conbench deployment before any storage-model change. The gate is
local-only and read-only. It is for migration confidence and sanitized scale
evidence, not for normal Conbench product workflow or committed deployment
infrastructure.

Do not commit passwords, tokens, `.pgpass` entries, service credentials,
private hostnames, private IP addresses, raw production-derived payloads, query
plans with identifiers, or raw server logs.

## What The Harness Proves

The compatibility harness checks the frozen legacy schema through the new
runtime:

- the server starts against the restored database,
- read APIs return valid data for series, results, history, compare, and CI
  report paths,
- the CLI can read the same server with `results get`, `series list`, and
  `compare`,
- the generated Python SDK can import and make basic read calls,
- writable table counts do not change,
- server logs do not contain blocked-write or read-only transaction errors.

Row-count checks catch writes that succeed. Log scanning catches write attempts
that the read-only role or `default_transaction_read_only` blocks. Both checks
are required for the no-write claim.

## Required Safety Boundary

Run the acceptance check with a dedicated read-only database role:

```bash
export CONBENCH_PROD_CLONE_DB_URL='postgresql://<read-only-role>@<clone-host>:<port>/<clone-database>'
export CONBENCH_PROD_CLONE_CONFIRM=read-only
export CONBENCH_PROD_CLONE_READONLY_ROLE='<read-only-role>'
```

`CONBENCH_PROD_CLONE_CONFIRM` must be exactly `read-only`. Any other value stops
the harness.

`CONBENCH_PROD_CLONE_READONLY_ROLE` must name the dedicated database role used
by the acceptance run. The harness also sets read-only connection options, but
the database role is the non-bypassable boundary.

If the connected server reports an address different from the URL host, use a
deployment-local allowlist:

```bash
export CONBENCH_PROD_CLONE_EXPECTED_HOSTS='<clone-host>,<server-reported-address>'
```

Keep that value outside committed documentation when it contains private
infrastructure names or addresses.

## Child Server Environment

The harness owns the child server environment. It sets:

- `CONBENCH_DB_URL` to a scrubbed read-only connection URL,
- `CONBENCH_ADDR` to the local listen address.

It must not inherit write-path, auth, session, seed, OIDC, GitHub token, or
fallback database variables from the caller. In particular, unset
`DATABASE_URL` for the child process so `CONBENCH_DB_URL` is the only database
target.

The restored legacy clone may not have rewrite-only tables such as `api_token`.
The harness treats legacy read-path tables as required and includes optional
rewrite tables in privilege and count checks only when they exist.

The validation script uses a hidden CLI helper inside the main `conbench`
binary. This helper is temporary and migration-only. It stays callable so
`scripts/prod_clone_compat.sh` and migration agents can run the gate, but it is
not listed in general CLI help and is not documented as a supported user
workflow. The repository does not build or ship a separate production-clone
executable.

## Running The Gate

From the repository root:

```bash
CONBENCH_PROD_CLONE_DB_URL='postgresql://<read-only-role>@<clone-host>:<port>/<clone-database>' \
CONBENCH_PROD_CLONE_CONFIRM=read-only \
CONBENCH_PROD_CLONE_READONLY_ROLE='<read-only-role>' \
scripts/prod_clone_compat.sh --profile
```

The script writes local artifacts under:

```text
var/prod-clone-compat/
```

Those artifacts are ignored by git. They may contain deployment-local paths,
sample identifiers, fingerprints, query plans, and server logs. Delete them
after extracting sanitized aggregate evidence:

```bash
rm -rf var/prod-clone-compat/
```

## Sanitized Findings

The latest profiled compatibility gate passed against a production-derived
legacy Postgres clone in the 100M-result-row class.

- Preflight was valid and acceptance-eligible before and after the run.
- API read probes passed for series list, benchmark result list/detail, history
  by result, history by fingerprint, benchmark-result compare, and CI report.
- CLI read probes passed for `results get`, `series list`, and `compare`.
- Python SDK smoke probes passed against the local server.
- Writable-table row-count comparison reported no changes.
- Server log scanning found zero blocked-write findings.

The largest relation observed was `public.benchmark_result`:

| Relation | Total | Heap | Indexes |
| --- | ---: | ---: | ---: |
| `public.benchmark_result` | 120.2 GB | 78.8 GB | 36.3 GB |

This confirms that the result table behaves like an analytical fact table. The
small dimension tables are not the source of the production-scale pressure.

## Read-Path Timings

Initial HTTP profiling with small page sizes showed targeted reads were viable
and unfiltered series browsing was the visible cost center:

| Read path | HTTP timing |
| --- | ---: |
| `/api/series?page_size=5` | 1.44-1.47 s |
| `/api/series?fingerprint=...&page_size=5` | 58-75 ms |
| `/api/history?fingerprint=...` | 35-51 ms |
| `/api/benchmark-results/{id}` | 5-16 ms |
| `/api/benchmark-results?page_size=5` | 6-7 ms |
| `/api/benchmark-results?earliest_timestamp=...&page_size=5` | 6-10 ms |
| `/api/compare/benchmark-results?...` | 60-72 ms |

A later browser probe used the web UI's normal page sizes and exposed DOM and
layout pressure:

| Browser path | Desktop timing | Mobile timing | Notes |
| --- | ---: | ---: | --- |
| Default browse | 43.9 s | 29.4 s | Web UI requested 50 series rows |
| Result detail | 0.6 s | 0.6 s | Loaded normally |
| Trend by result/fingerprint | 2.9-3.2 s | 2.9 s | Rendered full history table |
| Compare | 0.7-0.9 s | 0.7 s | Loaded normally |
| CI report | 5.2 s | 3.5 s | Rendered thousands of rows |

The browser evidence drove row caps, chunked rendering, and mobile table layout
hardening in the Svelte app.

## Post-Hardening Evidence

After bounded search/member-enrichment changes and UI row caps, the clone-backed
loopback run returned:

| Read path | Status | Timing |
| --- | ---: | ---: |
| `/api/runs/recent?page_size=25` | 200 | 0.28 s cold, 0.24 s warm |
| `/api/runs/recent?page_size=100` | 200 | 0.26 s cold, 0.24 s warm |
| `/api/series?page_size=5` | 200 | 1.37-1.38 s |
| `/api/series?page_size=10` | 200 | 1.75-1.79 s |
| `/api/series?page_size=50` | 200 | 3.3-6.0 s |
| `/api/series?q=<exact>&page_size=10` | 200 | 16.3 s cold, 1.7 s warm |
| `/api/series?q=<broad>&page_size=10` | 200 | 4.6 s cold, 2.8 s warm |
| `/api/ci/report?commit_sha=<sha>&repository=<repo>&run_ids=<run>` | 200 | 0.36-0.39 s |

The recent-runs SQL profile measured 395 ms for page size 25 and 238 ms for
page size 100. The plans used a bounded newest-result candidate scan over
`benchmark_result_timestamp_index`, then exact `run_id` aggregation through
`benchmark_result_run_id_index`. This confirms the v2 dashboard path avoids the
legacy Flask landing-page query shape that depended on 14-day predicates and
stale partial-index behavior.

The matching browser probe measured `/api/ci/report` at about 0.39 s for a
6.9 MB payload and the mobile CI report page at about 1.4 s after rendering the
initial 200 of 4,568 comparison rows.

A follow-up correctness review caught that sampling resultless recent commits
could produce sparse series pages. The first exact latest-per-fingerprint fix
restored correctness but timed out on the clone because it had to materialize
and sort the eligible result history. The current default browse path instead
starts from a bounded window of recent default-branch commits that actually have
non-errored benchmark results. Exact lookup remains the job of search,
fingerprint, run, history, and CI-report routes.

The follow-up clone smoke measured:

| Read path | Status | Timing |
| --- | ---: | ---: |
| `/api/series?page_size=5` | 200 | 3.4 s |
| `/api/series?page_size=25` | 200 | 3.8-4.0 s |
| `/api/series?page_size=50` | 200 | 6.2 s |
| `/api/series?hardware=<hardware>&page_size=5` | 200 | 6.1 s |
| `/api/benchmark-results?run_id=<run>&page_size=1` | 200 | 40 ms |

The matching browser smoke loaded `/series` with the Svelte loader's 25-row
page on desktop and mobile in about 4.1-4.2 s, with no console errors or
document-level horizontal overflow. This is still a browse cost center, but it
keeps the visible product path below the read timeout on the current schema.

The root causes addressed were:

- broad `q` search planning as a default-commit/result scan with case filtering
  applied too late,
- default browse planning as a global latest-per-fingerprint aggregation on the
  result fact table,
- list-row status and sparkline enrichment loading full histories for every
  visible series,
- the compatibility profiler measuring an obsolete unbounded diagnostic query
  instead of the bounded product query.

## Expected Warnings

Best-effort sample selection can still warn without failing the compatibility
gate:

- optional candidate-source queries may hit the statement timeout,
- optional sample metadata may hit the statement timeout,
- optional categories such as errored results, mixed units, or high-volume
  series may be absent from the sample manifest.

These warnings mean the evidence is strongest for compatibility and targeted
read cost. They are not proof that every historical data shape has been sampled.

## Storage Implications

Production-clone testing supports the staged storage roadmap:

- keep the frozen Postgres schema as the migration source of truth,
- keep targeted result, history, compare, and CI report paths bounded and fast,
- avoid building new product surfaces around broad fact-table browsing,
- use clone-derived evidence to decide whether and how to introduce a columnar
  analytical read replica.

The current conclusion is not that Postgres can remain the only analytical
store forever. The conclusion is that existing deployments can validate the new
runtime first, then evaluate a storage split from measured production-shaped
workloads.

## Recording Future Evidence

Record only sanitized aggregate findings in this documentation. Raw clone
artifacts stay under ignored `var/` paths unless they have been separately
reviewed and scrubbed.

Useful durable evidence includes:

- row-count and relation-size classes,
- request status and timing bands,
- whether row-count and blocked-write log-scan gates passed,
- browser DOM and layout aggregates,
- query-family conclusions that affect the storage roadmap.

Do not record sample result IDs, history fingerprints, private repository URLs,
private infrastructure details, credentials, or raw query plans.
