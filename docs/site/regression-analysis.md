# Regression Analysis

Conbench uses history-aware analysis to avoid treating every pairwise change as
a CI failure.

## Pairwise Change

Pairwise analysis compares a baseline result and contender result directly. It
is easy to understand and useful for display, but it can be noisy when a
benchmark has natural variance.

## Lookback Z-Score

Lookback analysis compares the contender against recent historical behavior for
the same series. A result is more meaningful when it deviates from the history
distribution, not just from one selected baseline value.

CI report status uses lookback z-score regression verdicts as the primary
failure signal. Pairwise analysis is still shown in report rows as useful
context.

## How Lookback Works

The analysis starts from the single value summary, or SVS, for each result. SVS
is the measured value on the submitted unit. Conbench applies the unit's
`less_is_better` setting to the published lookback z-score, so positive z-scores
mean better performance and negative z-scores mean worse performance.

Rolling history is calculated per history fingerprint. The window is the last
N distinct commit timestamps, not the last N result rows and not a wall-clock
interval. Commits with the same timestamp share one dense-rank window. This
keeps retries and multi-machine runs from changing the statistical window just
because they submitted more rows.

Conbench ports the legacy pandas behavior intentionally:

- rolling mean and standard deviation skip NaN values,
- standard deviation is sample standard deviation (`ddof=1`),
- a one-point window has no standard deviation and therefore no z-score,
- outlier and distribution-shift detection use clipped SVS differences before
  rolling statistics are calculated,
- JSON output uses `null` where the old pandas path produced NaN.

The raw intermediate z-score is `(SVS - rolling_mean) / rolling_stddev` when all
inputs are present and standard deviation is non-zero. For `less_is_better`
units, Conbench sign-normalizes that value before emitting it and applying
thresholds. Otherwise the row is `insufficient`.

## Thresholds

Both pairwise percent change and lookback z-score use strict thresholds. At the
default z threshold of `5.0`, a z-score must be less than `-5.0` to be a
regression or greater than `5.0` to be an improvement. Exactly `-5.0` or `5.0`
is not a verdict breach.

Pairwise percent change is useful for magnitude and quick inspection, but it
does not make a CI report fail by itself. That avoids failing a new or noisy
benchmark before enough history exists for the lookback model.

## Row Statuses

| Status | Meaning |
| --- | --- |
| `regressed` | Lookback analysis indicates a regression. |
| `improved` | Lookback analysis indicates an improvement. |
| `stable` | Enough history exists and no regression or improvement is indicated. |
| `insufficient` | Not enough history exists for z-score analysis. |
| `errored` | The benchmark result itself contains an error payload. |
| `missing_baseline` | No comparable baseline result was found. |
| `not_comparable` | Results differ in a way that prevents comparison. |

`skipped` CI reports are not failures. They mean Conbench found results, but no
row had enough history for z-score analysis.
