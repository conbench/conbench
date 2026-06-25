# Concepts

Conbench stores benchmark results as structured JSON and groups them into
history series that can be compared over time.

## Result

A result is one benchmark measurement payload. It contains:

- a benchmark case name and tags,
- a unit and observed data,
- machine or cluster hardware metadata,
- optional context and information tags,
- optional error details,
- run metadata such as `run_id`, `run_tags`, and `batch_id`,
- GitHub metadata such as repository, commit, branch, and pull request number.

The CLI write path accepts JSON files containing either one result object or an
array of result objects.

## Series

A series is a stable history of comparable results. The server derives a history
fingerprint from the benchmark case, context, hardware, and unit. The dashboard
uses series pages for trend inspection and regression context.

The history fingerprint is the product identity for a comparable benchmark
stream. Project health and regression summaries count series, not raw result
rows, so retries and multi-file submissions do not inflate the headline.

## Runs And Batches

Runs and batches are submitted metadata. Use `run_id` to group one benchmark
attempt, `run_tags` to attach workflow metadata, and `batch_id` when a
benchmark suite needs a wider grouping across related runs.

To inspect a run or batch, filter benchmark results by `run_id` or `batch_id`.
To compare a run against an inferred or explicit baseline, use a CI report with
`run_ids` and, when needed, `baseline_run_ids`.

## Commit Metadata

Commit metadata links a result to repository history. CI reports use repository
plus commit SHA to find contender runs and then choose a baseline using parent,
fork-point, or latest-default logic. Payloads must stamp the same commit SHA
that the CI job later passes to `conbench ci report`.

When the contender and baseline runs are already known, CI reports can compare
explicit run pairs through `run_ids` and `baseline_run_ids`. That mode uses the
same comparison rows and status rules without asking the server to infer an
ancestor baseline.

## Comparison

A comparison evaluates two compatible results. Conbench reports:

- pairwise percent change,
- lookback z-score analysis,
- stable, improved, regressed, insufficient, errored, missing-baseline, or
  not-comparable row statuses.

CI status is driven by lookback z-score regression behavior to reduce noisy
pairwise-only false positives.

## Project Health Vocabulary

The new dashboard treats regression state as current state, not as a one-time
event. A regression is open while the latest comparable point for a series is
outside the regression threshold. It closes when the series returns inside the
threshold band, improves past the improvement threshold, or is explicitly
re-baselined through a distribution-change annotation.

Health summaries use counts:

- `regressed`: latest comparable point is statistically worse,
- `improved`: latest comparable point is statistically better,
- `stable`: lookback analysis exists and is inside the threshold band,
- `insufficient`: not enough history exists to decide,
- `errored`: the latest relevant result has a benchmark error or cannot be
  analyzed.

Regressions and improvements are never netted against each other. A project with
ten regressions and ten improvements should not look healthy just because the
counts cancel. Always read health counts with their denominator, for example
`7 / 1,842 comparable series`, because the comparable universe changes as
benchmarks are added, removed, or filtered.

`missing` is only meaningful when there is an expected set, such as a selected
run or CI report. A historical fingerprint proves what has reported before; it
does not prove what should have reported in the current run.

Performance deltas are oriented so negative means worse and positive means
better, regardless of whether the raw unit is `less_is_better`.

## CLI-First Writes

The Go CLI is the canonical write path. It handles token resolution, payload
validation, multi-file submission, CI report rendering, and exit codes. Python
code can still construct payloads, but it should hand them to the CLI rather
than recreate the HTTP write client stack.
