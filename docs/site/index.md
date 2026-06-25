# Conbench

Conbench is a continuous benchmarking system for teams that need performance
data to be easy to submit, inspect, compare, and act on.

Benchmark projects send Conbench structured result JSON. Conbench stores those
results, groups comparable measurements into history series, and helps people
answer the questions that matter during development:

- what just ran,
- whether the run published the expected measurements,
- which benchmark series changed,
- whether a change is statistically meaningful,
- where to inspect the raw result, history, commit, and machine context.

The main surfaces are:

- a dashboard for browsing runs, results, series, trends, comparisons, and CI
  reports,
- the `conbench` CLI for submitting results and generating CI diagnostics,
- OpenAPI and generated SDKs for read automation,
- user-owned API tokens for CI and scripts,
- server-side alert rules for scheduled regression monitoring.

## What to do next

- New users: start with the [quickstart](quickstart.md).
- Benchmark authors: read [submitting results](submitting-results.md).
- CI owners: wire up [CI reporting](ci-reporting.md).
- Dashboard users: read [browsing and comparing](browsing-and-comparing.md) or
  review the [dashboard screenshots](dashboard-screenshots.md).
- CLI users: use the [CLI reference](cli-reference.md).
- Automation authors: use [API and SDK](api-and-sdk.md).
- Operators: review [operations](operations.md).

## Supported surfaces

| Need | Supported path |
| --- | --- |
| Submit benchmark results | `conbench results submit` |
| Generate a PR or CI diagnostic | `conbench ci report` |
| Manage scheduled regression alerts | server-side alert rules plus `conbench admin alerts evaluate` and `conbench admin alerts deliver` |
| Browse trends and comparisons | Svelte dashboard |
| Read/query from automation | Generated SDKs and OpenAPI |
| Authenticate humans | OIDC session login |
| Authenticate automation | User-owned API tokens |

## Migrating From Older Conbench

If you already run a Python/Flask Conbench deployment or publish results through
the older Python packages, start with the
[Python app migration guide](migration/python-app.md). The
[legacy parity roadmap](migration/legacy-parity-roadmap.md) explains what is
replaced, retired, or future product work. Package maintainers should use the
[legacy deprecation notices](migration/deprecation-notices.md) when updating
old READMEs, PyPI pages, or release notes.

Apache Arrow maintainers evaluating Buildkite-based migration should also read
the [Arrow workflow migration](migration/arrow-workflows.md) status page.
