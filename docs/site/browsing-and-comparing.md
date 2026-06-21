# Browsing And Comparing

The Svelte dashboard is the supported web interface.

## Series Browse

The home page summarizes recent benchmark activity. Use it to answer: what just
ran, how much data did it publish, did any results error, and where is the CI
report or a sample result?

The series explorer lives at `/series`. Use it to find benchmark families,
filter by search text, and navigate to trend pages. Series rows show recent
state, latest result metadata, and a compact history summary.

The home dashboard groups activity by submitted `run_id` values, with direct
links to run detail, batch detail, CI reports, and sample results. Batch pages
are available at `/batches/<batch_id>` when you need to inspect a suite-level
grouping across multiple runs.

Use the hardware filter to find benchmark series for a machine or cluster name.
Hardware is part of result and series context, so hardware investigation starts
from benchmark activity rather than from a standalone catalog.

The browse surface is designed for scanning. It favors full-width table rows,
filters, and direct links over card grids or nested summary panels. Broad
queries can match many production series, so pages cap rendered rows and ask you
to narrow with search, hardware, repository, fingerprint, or active-time filters
instead of painting an unbounded table.

Default browse is intentionally a recent discovery view. On large installations
it starts from a bounded window of recent default-branch commits that have
benchmark results, then shows the latest visible member for each series. Use a
search term, a known history fingerprint, a run page, or a CI report when you
need an exact historical lookup for a specific benchmark family.

Benchmark-name search shows a loaded family drilldown: case variants,
hardware/context coverage, loaded history-point counts, and
regressed/improved triage links. It is intentionally scoped to the loaded rows
so it remains usable on large installations; load more or narrow the filters
when you need broader coverage.

Use loaded triage links, CI reports, and per-series outlier/step shortcuts to
investigate current signals. Whole-family analytics should be treated as a
scale-aware product workflow rather than as an unbounded table.

## Trend Detail

A trend page shows the result history for one fingerprint. It is the primary
place to inspect:

- recent values,
- outliers,
- z-score context,
- result links,
- commit metadata,
- manual baseline and contender picks.

Trend pages are the canonical place to localize a regression. They show the
commit-ordered series, rolling history context, result links, and point flags
for one fingerprint. Large histories are rendered progressively: the recent
window appears first, with controls to reveal more history when needed.

Use the outlier and step filters when a long history needs triage. Filtering is
applied before the rendered-row cap, so an old flagged point can still be found
without revealing the full table. Selecting a point opens an inspector with the
result id, commit, z-score, flags, result link, compare-pick buttons, and a
copyable `conbench history export` command for the same series. The benchmark
identity, range controls, summary counts, filters, and compare picks stay pinned
as one context band while you scroll through a long table.

Benchmark errors are surfaced on result detail, run detail, batch detail, and CI
report pages. The trend history endpoint is value-history oriented and does not
currently include errored benchmark attempts as history points.

## Result Detail

Use `/results` when you need a bounded, human-readable list of submitted
benchmark results. The page filters by `run_id`, `batch_id`, `run_reason`, and
timestamp bounds, then links each loaded row to result detail, run detail, batch
detail, and the series trend.

Result detail pages show the raw result payload interpreted by the API:
case tags, context, info, hardware, run metadata, GitHub metadata, unit, data,
validation, and errors.

The result page also exposes investigation fields that are easy to lose in a
summary UI: hardware hash, history fingerprint, optional benchmark info,
validation, change annotations, raw data/times counts, and the full JSON
payload. Authenticated users can mark or unmark `begins_distribution_change`
and delete a result through the dashboard; both actions call the same
authenticated result APIs used by automation.

Use **Export history JSON** on a result page when the browser workflow needs the
raw history API response for that result. Use the CLI when you need a history
CSV file.

For automation and notebook workflows, the result-list API can be filtered by
run or batch metadata:

```bash
curl "$CONBENCH_SERVER_URL/api/benchmark-results?run_id=$RUN_ID"
curl "$CONBENCH_SERVER_URL/api/benchmark-results?batch_id=$BATCH_ID"
```

Use `run_id` when you want one submitted run, and `batch_id` when you want the
related runs that a benchmark suite grouped together. Runs and batches are
submitted metadata, not separate storage objects, but the dashboard exposes
first-class inspection pages over those result-list filters.

The run detail dashboard at `/runs/<run_id>` lists bounded result pages for one
submitted run, summarizes loaded results/errors/series/batches, and links to the
run's CI report, result details, and series trends.

The batch detail dashboard at `/batches/<batch_id>` lists bounded result pages
for one submitted batch, groups loaded rows by `run_id`, and links to run
detail, CI reports, result detail, and series trends.

## History CSV Export

Use the CLI when you need a history CSV file:

```bash
conbench history export "$RESULT_ID" \
  --server "$CONBENCH_SERVER_URL" \
  --output history.csv
```

Without `--output`, the CSV is written to stdout. The CSV is generated from the
same JSON history API that powers trend pages. Trend pages show a copyable CLI
command for the selected point or entry result, and result pages link directly
to the JSON history response.

## Compare

The compare page evaluates two benchmark results. Use it for manual inspection
or links from CI report rows. The comparison includes pairwise change and
lookback z-score analysis where enough history exists.

Single-result compare expects the two results to belong to the same history
fingerprint, which keeps the pairwise value and lookback history tied to the
same benchmark series. Open `/compare` directly when you already know result
IDs, or load bounded candidate rows by `run_id` and select the baseline and
contender from the picker. The picker validates known fingerprints before
navigation; the compare API remains the source of truth for manually typed IDs.
Use CI reports for run-to-run and commit-wide comparisons.

## CI Report

The CI report page groups comparisons for a commit or run selector. It is the
web counterpart to `conbench ci report` and should be the first dashboard link
people open from pull request logs.

Use the status buttons, hardware selector, and search box to narrow a large
report to the rows that need attention. The issue shortcuts jump directly to
the first visible regression, benchmark error, missing baseline, or
not-comparable row, and each run section keeps its own filtered summary.

Large CI reports filter first, then render a bounded row set and reveal
additional matching rows on demand. The report summary always describes the
whole report; row rendering limits are only a browser-performance guard.

For manual run-to-run inspection, open a CI report URL with `run_ids` and
`baseline_run_ids`. This uses the same CI report surface and row-status rules
as pull request diagnostics.
