# The "lookback z-score method" of benchmark result analysis

A core value of Conbench is the ability to compare incoming benchmark results with historic results to make data-driven decisions about performance. The primary method of doing this in Conbench is the "lookback z-score" analysis. This page describes how that process works.

## Overview

The lookback z-score analysis assigns a numeric z-score value to a benchmark result that represents how "good" the result is compared to a historic distribution of similar results. Coupled with a threshold, this can be used to determine whether the benchmark result is indicative of a performance regression or improvement.

## Choosing the historic distribution of results

When scoring a contender benchmark result, to control for variables that don't have to do with actual performance changes, each result in the historic distribution must share the contender's:

- repository
- hardware
- case
- context

Results with errors will not be included, even if they also have data.

Additionally, when using the lookback z-score method, one must provide a baseline commit (or baseline result or baseline run, which is ultimately associated with a baseline commit). The historic distribution will be drawn from all runs on commits in the baseline commit's git ancestry, up to and including all runs on the baseline commit itself. The maximum number of commits used is defined by the Conbench server's `DISTRIBUTION_COMMITS` parameter, which defaults to 100. In certain cases, there will be fewer than this number: if there are not that many commits in the ancestry, or if a distribution change was annotated by someone acting as a data curator -- see below for more details.

In some cases (e.g. navigating the UI, or generating alerts with the `benchalerts` library), Conbench will provide the user with a sensible baseline commit. If the contender is on a PR branch, the sensible baseline commit is the point at which the PR branch forked from the default branch. If the contender is on the default branch, the sensible baseline commit is the parent commit.

If there are no matching results on the baseline commit, that's alright - the analysis will still include matching results from the git history. If there are multiple results on the baseline commit (from different runs, etc.), all of them will be used.

## Creating the z-score
