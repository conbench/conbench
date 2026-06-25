# Arrow Workflow Migration

This page describes the current Conbench v2 migration path for Apache Arrow
benchmark workflows. It is written for maintainers evaluating the new system,
not for people who built the previous Python application.

The migration is not complete until it has been validated against a
non-production Conbench v2 deployment and Buildkite. Production-shaped read
validation has passed against a restored clone; use this page as the public
checklist for the remaining evaluation.

## Current Direction

Arrow keeps Buildkite as the benchmark task queue and log-capture system.
Conbench v2 owns result ingestion, dashboard investigation, CI report selection,
and optional GitHub Check Run or pull request comment publishing.

The intended flow is:

1. Buildkite runs a benchmark job.
2. The benchmark repository writes Conbench v2 result payload JSON.
3. The job submits payloads with `conbench results submit`.
4. The job runs `conbench ci report` when pull request feedback is needed.
5. Maintainers inspect results, runs, series, and CI reports in the dashboard.

This keeps benchmark execution in the benchmark projects. It avoids reviving the
retired Python client stack as a compatibility layer.

## Temporary Evaluation Forks

The current evaluation work uses public forks and branches:

| Repository | Branch | Purpose |
| --- | --- | --- |
| [`wesm/arrow-benchmarks-ci`](https://github.com/wesm/arrow-benchmarks-ci/tree/v2-conbench-ci-report) | `v2-conbench-ci-report` | Buildkite scheduling, smoke tests, artifact capture, result submission, and CI report handoff. |
| [`wesm/benchmarks`](https://github.com/wesm/benchmarks/tree/v2-conbench-submit) | `v2-conbench-submit` | Python benchmark payload emission for Conbench v2. |
| [`wesm/arrowbench`](https://github.com/wesm/arrowbench/tree/v2-conbench-payloads) | `v2-conbench-payloads` | R benchmark payload emission for Conbench v2. |
| [`conbench/conbench`](https://github.com/conbench/conbench/tree/experimental-v2) | `experimental-v2` | Go server, Svelte dashboard, CLI, generated SDKs, and migration documentation. |

These branches are evaluation surfaces, not permanent fork policy. Once the path
is accepted, maintainers can decide how to upstream or replace them.

## Required Secrets And Environment

Conbench reporters authenticate with server-minted API tokens. Operators mint a
reporter token from the Conbench server environment or an admin job with
database access:

```bash
CONBENCH_DB_URL="$CONBENCH_DB_URL" conbench admin tokens create \
  --email ci@example.com \
  --user-name "Conbench CI Reporter" \
  --token-name buildkite
```

Store only the returned plaintext token in Buildkite as `CONBENCH_TOKEN`.

Benchmark jobs need:

| Name | Secret | Purpose |
| --- | --- | --- |
| `CONBENCH_URL` | no | Non-production Conbench v2 endpoint during evaluation. |
| `CONBENCH_TOKEN` | yes | Reporter API token used by `conbench results submit` and `conbench ci report`. |
| `CONBENCH_CLI` | no | Path or executable name for the v2 CLI. |
| `CONBENCH_SUBMIT_JOBS` | no | Submit parallelism for large suites. Defaults to `64` in the Buildkite fork for one-file-per-result workloads; lower it if the endpoint or database shows pressure. |
| `BENCHMARKABLE` | no | Commit SHA being benchmarked. |
| `BENCHMARKABLE_PR_NUMBER` | no | Pull request number for PR-shaped runs. |
| `RUN_ID` | no | Stable run identifier, usually the Buildkite build ID. |
| `RUN_NAME` | no | Human-readable run label. |
| `RUN_REASON` | no | `pull-request`, `nightly`, `manual-smoke`, or similar. |
| `MACHINE` | no | Stable benchmark machine name. |

GitHub publishing also needs a GitHub App installed on the target repository
with permission to create Check Runs and pull request comments:

| Name | Secret | Purpose |
| --- | --- | --- |
| `CONBENCH_CI_GITHUB_APP_ID` | no | GitHub App ID. |
| `CONBENCH_CI_GITHUB_APP_PRIVATE_KEY` | yes | PEM private key contents. |

Validate GitHub publishing against a scratch pull request before using
production Apache Arrow pull requests.

## Smoke Order

Run evaluation in this order:

1. Adapter preflight in `wesm/arrow-benchmarks-ci`.
   This writes one synthetic v2 payload and submits it to a non-production
   Conbench endpoint. It proves the token, CLI, endpoint, network, and artifact
   path before a long benchmark build starts.
2. One Python benchmark smoke from `wesm/benchmarks`.
   Use a small filter first, then expand only after submit and artifact behavior
   is visible.
3. One R benchmark smoke from `wesm/arrowbench`.
   Confirm generated payloads use RFC3339 timestamps, numeric stats, and stable
   machine metadata.
4. CI report without GitHub publishing.
   Confirm missing baselines are reported as an `action_required` result, not as
   authentication or transport errors.
5. GitHub App publishing against a scratch pull request.
   Submit a scratch-shaped payload whose `github.repository`, `github.commit`,
   and pull request number match the scratch target, then confirm the Check Run
   and pull request comment appear only there. Do not mix Arrow run IDs with a
   scratch repository selector.
6. Scheduler-path Buildkite smoke.
   Confirm the scheduled path can create a benchmark build, retain logs and
   artifacts, and hand off report metadata.
7. Production-clone validation.
   Confirm recent-run dashboard queries, result browsing, series pages, CI
   report selection, and representative submit paths against production-shaped
   data.

The [temporary production-clone migration gate](../prod-clone-compatibility.md)
page describes the read-only production-clone gate. The Buildkite fork's
[`docs/v2-conbench-smoke-test-plan.md`](https://github.com/wesm/arrow-benchmarks-ci/blob/v2-conbench-ci-report/docs/v2-conbench-smoke-test-plan.md)
contains the detailed Buildkite smoke commands.

## What Is Already Exercised Locally

Local smoke runs have shown that:

- the Go CLI submits multiple result objects with bounded concurrency,
- one JSON file may contain either one payload object or an array of payload
  objects,
- the Python benchmark fork can emit and submit a representative v2 payload,
- the R benchmark fork can emit and submit non-error v2 payloads,
- the Buildkite adapter preflight can emit an environment-shaped v2 payload, and
- server-minted reporter tokens are the intended automation auth path.

The read-only production-clone gate has also passed on a 100M-result-row class
Postgres restore. Recent-runs dashboard requests returned in about 0.24-0.28 s,
CI report selection returned in about 0.37-0.39 s, and targeted result/history/
compare probes passed through the API, CLI, and generated Python SDK.

Those checks reduce migration risk, but they do not replace Buildkite execution,
GitHub App publishing, or a non-production deployment that maintainers can
evaluate directly.

## Caveats For Existing Deployments

Existing data stays in the frozen Postgres schema, but deployment migration is
operational work. Maintainers should plan for:

- a parallel Conbench v2 deployment pointed at production-shaped data before
  cutover,
- OIDC configuration for human login,
- reporter-token minting and secret rotation for Buildkite,
- GitHub App installation and repository permissions for PR feedback,
- benchmark-machine environment changes for the v2 CLI and payload directories,
- dashboard and query latency checks against the real data shape, and
- a clear rollback or pause point before production pull requests receive new
  Conbench comments.

The migration path should become turnkey only after these checks have evidence.
