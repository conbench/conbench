"""Message formatting helpers for alerts."""

import textwrap
from typing import List, Optional

from .conbench_dataclasses import BenchmarkResultInfo, FullComparisonInfo


def _clean(text: str) -> str:
    """Clean text so it displays nicely as GitHub Markdown."""
    return textwrap.fill(textwrap.dedent(text), 10000).replace("  ", "\n\n").strip()


def _list_results(benchmark_results: List[BenchmarkResultInfo]) -> str:
    """Create a Markdown list of benchmark result information."""
    out = ""
    previous_run_id = ""

    for benchmark_result in benchmark_results:
        # Separate each run into a section, with a title for the run
        if benchmark_result.run_id != previous_run_id:
            out += (
                f"\n\n- {benchmark_result.run_reason.title()} Run at "
                f"[{benchmark_result.run_time}]({benchmark_result.run_link})"
            )
            previous_run_id = benchmark_result.run_id
        out += f"\n  - [{benchmark_result.name}]({benchmark_result.link})"

    if out:
        out += "\n\n"

    return out


def github_check_summary(
    full_comparison: FullComparisonInfo, warn_if_baseline_isnt_parent: bool
) -> str:
    """Generate a Markdown summary of what happened regarding errors and regressions."""
    sha = full_comparison.contender_sha[:8]
    summary = ""

    if full_comparison.benchmarks_with_errors:
        summary += _clean(
            """
            ## Benchmarks with errors

            These are errors that were caught while running the benchmarks. You can
            click the link next to each result to go to the Conbench entry for that
            benchmark, which might have more information about what the error was.
            """
        )
        summary += _list_results(full_comparison.benchmarks_with_errors)

    summary += "## Benchmarks with performance regressions\n\n"

    if full_comparison.no_baseline_runs:
        summary += _clean(
            f"""
            Conbench could not find a baseline run for contender commit `{sha}`. A
            baseline run needs to be on the default branch in the same repository, with
            the same hardware, and have at least one of the same benchmark case/context
            pairs as one of the runs on the contender commit.
            """
        )
        # exit early
        return summary

    summary += _clean(
        f"""
        Contender commit `{sha}` had
        {len(full_comparison.benchmarks_with_z_regressions)} performance regression(s)
        compared to its baseline runs.
        """
    )
    summary += "\n\n"

    if full_comparison.benchmarks_with_z_regressions:
        summary += "### Benchmarks with regressions:"
        summary += _list_results(full_comparison.benchmarks_with_z_regressions)

    if full_comparison.no_baseline_is_parent and warn_if_baseline_isnt_parent:
        summary += _clean(
            """
            ### Note

            No baseline run was on the immediate parent commit of the contender commit.
            See the link below for details.
            """
        )

    return summary


def github_check_details(full_comparison: FullComparisonInfo) -> Optional[str]:
    """Generate Markdown details of what happened regarding regressions."""
    if full_comparison.no_baseline_runs:
        return None

    details = _clean(
        f"""
        Conbench has details about {len(full_comparison.run_comparisons)} total run(s)
        on this commit.

        This report was generated using a z-score threshold of
        {full_comparison.z_score_threshold}. A regression is defined as a benchmark
        exhibiting a z-score higher than the threshold in the "bad" direction (e.g. down
        for iterations per second; up for total time taken).
        """
    )
    return details
