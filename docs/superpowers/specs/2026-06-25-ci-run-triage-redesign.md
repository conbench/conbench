# CI Run Triage Redesign

Date: 2026-06-25

## Problem

The v2 Svelte app exposes storage and implementation identifiers too early. In
production-shaped Arrow data this creates pages dominated by run IDs, batch IDs,
result IDs, and raw text filters. Maintainers comparing the app with the legacy
Conbench UI cannot quickly answer the operational questions they care about:

- What ran recently?
- Which commits and authors are involved?
- Which hardware targets produced results?
- Which runs need attention?
- Where is the CI report or comparison context?
- Which benchmark family should I inspect next?

The first redesign milestone should restore CI run triage. Benchmark directory
and series search improvements remain important but are a separate immediate
follow-up.

This milestone is not blocked on storage changes. The frozen schema already
persists commit message, author name, author login, and author avatar metadata;
the current recent-runs list query simply does not expose those fields yet. The
detail path already selects commit message, so the implementation should extend
the existing read model rather than inventing a parallel identity model.

## Goals

- Make the home page a CI-run triage surface for `apache/arrow` by default.
- Lead with human-readable commit, author, message, reason, hardware, result
  count, and report status.
- Use existing bounded attention data honestly: show regressions/report
  attention for the newest attention window only, currently five runs, not as a
  page-wide truth.
- Keep UUIDs available for copy/debug/deep links, but make them secondary.
- Provide obvious entry points to CI reports, run detail, sample result, and
  benchmark trends.
- Avoid raw free-text filter boxes for values users cannot reasonably know.
- Keep the first pass read-only and safe against the production RDS evaluator.

## Non-Goals

- Do not redesign the full benchmark directory in this milestone.
- Do not implement fast faceted `/series` search in this milestone.
- Do not add write workflows, token minting, or reporter submissions.
- Do not add public AWS exposure or DNS.
- Do not recreate the legacy Flask UI one-for-one.

## Home Page

The home route (`/`) should become a CI runs dashboard, not a generic recent
activity table.

Primary content:

- Page title: `CI runs`
- Repository context: display a static `apache/arrow` label for this milestone.
  A repository selector requires a repository listing and filtering API and
  belongs with the benchmark directory/faceted search follow-up.
- Compact summary row:
  - number of recent runs
  - total results
  - errors across the loaded recent runs
  - attention shown for the newest bounded attention window, currently five runs
- Optional attention strip, visible only when failures, regressions, action
  required reports, benchmark errors, missing baselines, or non-comparable
  reports exist in the bounded attention window.

Primary table columns:

- `time`: newest result time for the run, linked to run detail.
- `results`: result count and error count for every row. Regression/report
  attention badges appear only for rows where bounded attention was computed.
- `reason`: raw `run_reason` value with light formatting only after production
  values are verified. Do not invent a fixed taxonomy in the UI.
- `hardware`: readable machine name when available from the selected/latest
  result. Run-wide hardware aggregation is net-new and should not be required
  for the first page unless the backend query is proven bounded and fast.
- `author`: avatar and display name when GitHub metadata exists.
- `commit`: short hash, linked to GitHub when repository and SHA are available.
- `message`: commit subject, wrapped to a useful width.
- `report`: CI report status and link when the run is reportable.

The table should be dense enough for repeated maintainer use. Avoid large cards,
marketing-style hero copy, and rows where the primary link text is a UUID.

## Run Detail Page

The run detail route should explain the run before exposing raw result rows.

Header:

- Primary heading should be commit subject or a readable run label.
- Secondary metadata should include short commit, author, reason, hardware
  summary, result count, and latest run time.
- `run_id` should be in a secondary copyable field, not the heading.

Context panel:

- repository
- commit hash and GitHub link when available
- run reason
- hardware summary
- loaded result/window summary
- CI report action if available

Results table:

- Lead with benchmark name and parameters, not result ID.
- Include hardware, status, SVS, unit, batch/time, and trend/detail actions.
- Result IDs remain visible as subdued copyable metadata or in a details column,
  not as the primary row identity.

## Results Page

The results route can remain a raw-result explorer, but it should not be the
main maintainer entry point.

Minimum change for this milestone:

- If linked from a run, preserve run context in the header.
- Use benchmark name and hardware as primary row labels.
- Move result IDs to secondary metadata.

## Data Requirements

The existing recent-runs API provides part of the required data, but the UI
needs a richer view model for high-quality triage.

Preferred backend shape:

- Extend `/api/runs/recent` rather than adding a parallel endpoint. Attention
  already lives on this route, and keeping pagination, result counts, errors,
  and attention in one path avoids duplicated query plumbing.
- Include commit author name/avatar when available.
- Include commit subject/message.
- Build GitHub commit URLs client-side from repository and SHA. No backend field
  is needed for this.
- Include report status/attention summary only through the existing bounded
  attention path. In the current service this is intentionally limited to the
  newest attention window, currently five runs.
- Treat run-wide hardware summaries as the riskiest new data requirement.
  Hardware is currently per-result, so a distinct or grouped summary across a
  run needs an explicitly bounded/indexed design and production-shaped timing
  before the home page depends on it. Prefer omitting or showing latest-result
  hardware in the first implementation if that keeps the page fast.

The endpoint must be designed for the page rather than forcing the Svelte app to
fan out across hundreds of runs or results. Avoid client-side N+1 API calls.

## Performance

- Initial home load should return quickly on production data.
- Do not issue broad `/series` searches from the home page.
- The attention summary should use the existing bounded attention/report query
  path. A repo-wide "runs needing attention" count is a separate backend
  feature and should not be implied by this milestone.
- Any hardware aggregation across a run must be benchmarked against
  production-shaped Arrow data before it is wired into first paint.
- Slow search failures should render a clear retry/error state without leaving
  the page visually empty.

## Interaction Design

- Replace raw hardware/repository text boxes in future series work with facets
  or autocomplete. In this milestone, avoid adding more raw filters.
- Treat `run_reason` as a nullable free string. In the private evaluator sample
  checked on 2026-06-25, recent Arrow runs only showed `commit`; broader
  production distinct-value verification should happen before adding friendly
  labels beyond direct display.
- Table links should name the domain object: CI report, run detail, trend,
  result detail, GitHub commit.
- UUIDs should be truncated, copyable, and labeled when shown.
- Empty and loading states should not occupy the whole viewport with low-value
  copy.

## Accessibility

- Preserve semantic tables for tabular data.
- Use link text that describes the destination.
- Do not rely on color alone for report/attention state.
- Ensure dense tables still work at mobile widths through stacked rows or
  horizontal scrolling with stable column sizes.

## Testing

Tests should verify behavior and data transformation, not literal prose.

Suggested coverage:

- Loader/transform tests for CI-run summary view models.
- View-model tests proving that a run row with commit subject/author data
  derives a human-readable primary label, while `run_id` remains available as a
  secondary metadata field. Do not assert tautological DOM text placement or
  class names as content coverage.
- Attention-state tests for regressions, errors, action required, and clean runs.
- API tests for bounded summary output and error handling.
- Playwright or screenshot smoke against seeded data for desktop/mobile layout
  after implementation.

## Rollout

1. Implement the data/view-model path for CI run summaries.
2. Replace the current home table with the CI runs dashboard.
3. Update run detail to demote UUIDs and lead with benchmark/commit context.
4. Verify stored `author_avatar` values before rendering avatars; the column is
   bounded to 100 characters and may contain truncated URLs. If values are
   missing or unusable, render author name/login without an external image.
   Rendering avatars also makes browsers fetch GitHub-hosted images, so keep it
   optional rather than a required identity signal.
5. Smoke on the private AWS evaluator using production-backed read-only data.
6. Capture follow-up issues for benchmark directory and fast faceted series
   search.
