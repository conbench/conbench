# Legacy Parity Roadmap

This page is not a compatibility contract. It records what the new Conbench
keeps, replaces, retires, and may build later after deleting the legacy
Flask/Jinja application and old Python package stack.

The migration goal is to preserve useful jobs, data, and analysis behavior, not
old route names, import paths, or password-era operational patterns. Existing
deployments should migrate to the documented Go API, Svelte dashboard, Go CLI,
generated SDKs, and server-owned alerting surfaces.

## Principles

- Keep the frozen Postgres schema readable while moving product behavior into
  the Go server and Svelte dashboard.
- Use the `conbench` CLI as the canonical write and CI path.
- Use generated SDKs for reads and automation, not hand-maintained password
  clients.
- Replace legacy dashboard jobs with new dashboard workflows when the job is
  still useful.
- Retire low-value catalogs, cache-era views, and source-compatible Python imports
  unless a real migration proves the need for a narrower helper.
- Treat production-scale behavior as part of parity. A page that worked only
  through the old BMRT cache is not automatically a good target for a direct
  port.

## Replaced Workflows

| Legacy job | New supported path |
| --- | --- |
| Submit benchmark results with `benchconnect` or direct POST helpers | Write one result object per JSON file and run `conbench results submit`; Python jobs may use `conbench.migration` for payload-file writing and CLI invocation. Follow the [migration guide](python-app.md) and the runnable [`examples/migration/gbench_to_cli_submit.py`](https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py) recipe. |
| Run PR regression checks with `benchalerts` | Run `conbench ci report`, publish Markdown through CI, and use its exit code for status. |
| Deliver scheduled alert notifications from Python | Use server alert rules, `conbench admin alerts evaluate`, and `conbench admin alerts deliver` for webhook, Slack, GitHub Check, GitHub commit-comment, or email delivery. |
| Browse recent runs from the Flask landing page | Use the Svelte home dashboard, run pages, batch pages, CI report links, and sample result links. |
| Inspect one result from `/benchmark-results/{id}/` or `/benchmarks/{id}/` | Use `/results/{id}` or `/benchmark-results/{id}` with raw metadata, history JSON, validation, hardware, run, commit, and authenticated result actions. |
| Browse submitted results | Use `/results`, `/api/benchmark-results?...`, generated SDK list operations, run pages, and batch pages. |
| Inspect a run or batch page | Use `/runs/<run_id>` and `/batches/<batch_id>`, backed by result-list filters and CI report links. |
| Download history CSV | Use `conbench history export <result-id>`; dashboard pages expose JSON history and copyable export commands. |
| Compare two result IDs | Use `/compare?baseline=<id>&contender=<id>` or the compare API, with stricter same-fingerprint semantics. |
| Compare run pairs | Use `conbench ci report --run-ids ... --baseline-run-ids ...` or the `/ci/report` dashboard URL. |
| Browse conceptual benchmark families | Use `/series`, `/series?q=<benchmark>`, loaded family drilldown, and per-series trend pages. |
| Manage current-user identity and tokens | Use OIDC login, `/account`, `/api/users/me`, `/api/tokens`, and `conbench auth ...`. |

## Retired Surfaces

| Retired surface | Reason |
| --- | --- |
| Source-compatible `benchadapt`, `benchconnect`, `benchclients`, `benchrun`, `benchalerts`, and `conbenchlegacy` imports | They would preserve the old client design and maintenance burden. Migration uses JSON payloads, the Go CLI, generated SDKs, and documented examples. |
| Password login, registration keys, and arbitrary user CRUD pages | Human auth is OIDC-based. User-owned API tokens and alert rules are self-service under `/account`. Future operator administration should be a new authenticated admin feature. |
| Standalone hardware, commits, contexts, and info catalogs | The useful data appears inside result, series, trend, run, batch, and CI workflows. Standalone catalogs did not justify route compatibility. |
| Loose cross-fingerprint result comparison | The new compare path expects the same history fingerprint so pairwise and lookback analysis describe the same benchmark series. |
| Old BMRT global slope-ranking page | It was a cache-era view that does not fit the 100M-row production shape. Current triage uses loaded family summaries, CI reports, and per-series outlier/step filters. |
| Flask/Jinja route aliases | New dashboard routes are product surfaces, not compatibility aliases. Add aliases only with explicit approval and a documented maintenance reason. |
| Legacy Selenium screenshot capture | Documentation screenshots now use the reproducible Docker/Playwright harness behind `make docs-screenshots`. |

## Product Roadmap Candidates

These are not compatibility promises. They are the remaining useful ideas that
may deserve new product work if users need them.

| Candidate | Trigger to build |
| --- | --- |
| Scale-aware whole-family analytics | Users need a replacement for cross-series family triage that works on production-sized data without resurrecting the BMRT cache. |
| Richer Arrow/archery migration recipe | A real Arrow migration exposes archery-specific metadata or adapter behavior not covered by the Google Benchmark fixture demo. |
| Operator administration dashboard | Operators need managed user or deployment administration beyond current-user `/account` self-service. |
| Storage/read-model redesign | Production-clone evidence shows a current read workflow cannot meet scale goals on the frozen schema with query/index work alone. |

## Decision Checklist

When a legacy parity request appears, classify it before building:

1. Is the user job already covered by a documented Go/Svelte/CLI/SDK path?
2. If not, is the job still useful in the new product, or was it only an old
   implementation artifact?
3. Can it work at production scale without reviving the old cache or Python
   runtime?
4. Does it need a new product feature, a migration recipe, or just clearer
   documentation?
5. Would a source-compatible shim create long-term maintenance cost? If yes,
   get explicit approval before adding it.

The [migration guide](python-app.md) is the step-by-step path for users. Treat
this roadmap as the public status page for legacy parity decisions; lower-level
implementation tracking does not belong in the public documentation site.
