"""Message formatting helpers for alerts."""

import textwrap
from typing import List, Optional

from .conbench_dataclasses import BenchmarkResultInfo, FullComparisonInfo


def _clean(text: str) -> str:
    """Clean text so it displays nicely as GitHub Markdown."""
    return textwrap.fill(textwrap.dedent(text), 10000).replace("  ", "\n\n").strip()


class _Pluralizer:
    """Depending on the length of the input list, return the correct pluralization
    suffixes and plural forms of special English words.
    """

    def __init__(self, some_list: list) -> None:
        self.plural = len(some_list) != 1

    @property
    def were(self):
        return "were" if self.plural else "was"

    @property
    def s(self):
        return "s" if self.plural else ""


def _run_bullet(reason: str, time: str, link: str) -> str:
    return f"- {reason.title()} Run at [{time}]({link})"


def _list_results(
    benchmark_results: List[BenchmarkResultInfo], limit: Optional[int] = None
) -> str:
    """Create a Markdown list of benchmark result information."""
    out = ""
    previous_run_id = ""

    for ix, benchmark_result in enumerate(benchmark_results):
        if limit and ix >= limit:
            number_unlisted = len(benchmark_results) - limit
            out += f"\n- and {number_unlisted} more (see the report linked below)"
            break

        # Separate each run into a section, with a title for the run
        if benchmark_result.run_id != previous_run_id:
            out += "\n\n"
            out += _run_bullet(
                benchmark_result.run_reason,
                benchmark_result.run_time,
                benchmark_result.run_link,
            )
            previous_run_id = benchmark_result.run_id
        out += f"\n  - [{benchmark_result.name}]({benchmark_result.link})"

    if out:
        out += "\n\n"

    return out


def github_check_summary(full_comparison: FullComparisonInfo) -> str:
    """Generate a Markdown summary of what happened regarding errors and regressions."""
    hash = full_comparison.commit_hash[:8]
    summary = ""

    if full_comparison.benchmarks_with_errors:
        summary += _clean(
            """
            ## Benchmarks with errors

            These are errors that were caught while running the benchmarks. You can
            click each link to go to the Conbench entry for that benchmark, which might
            have more information about what the error was.
            """
        )
        summary += _list_results(full_comparison.benchmarks_with_errors)

    summary += "## Benchmarks with performance regressions\n\n"

    if full_comparison.no_baseline_runs:
        summary += _clean(
            """
            There weren't enough matching historic runs in Conbench to make a call on
            whether there were regressions or not.

            To use the lookback z-score method of determining regressions, there need to
            be at least two historic runs on the default branch which, when compared to
            one of the runs on the contender commit, are on the same hardware, and have
            at least one of the same benchmark case and context pairs.
            """
        )
        # exit early
        return summary

    s = _Pluralizer(full_comparison.benchmarks_with_z_regressions).s
    summary += _clean(
        f"""
        Contender commit `{hash}` had
        {len(full_comparison.benchmarks_with_z_regressions)} performance regression{s}
        using the lookback z-score method.
        """
    )
    summary += "\n\n"

    if full_comparison.benchmarks_with_z_regressions:
        summary += "### Benchmarks with regressions:"
        summary += _list_results(full_comparison.benchmarks_with_z_regressions)

    summary += f"## All benchmark runs on commit `{hash}`\n"
    for comparison in full_comparison.run_comparisons:
        summary += "\n"
        summary += _run_bullet(
            comparison.contender_reason,
            comparison.contender_datetime,
            comparison.contender_link,
        )

    return summary


def github_check_details(full_comparison: FullComparisonInfo) -> Optional[str]:
    """Generate Markdown details of what happened regarding regressions."""
    if full_comparison.no_baseline_runs:
        return None

    details = _clean(
        f"""
        This report was generated using the lookback z-score method with a z-score
        threshold of {full_comparison.z_score_threshold}.
        """
    )
    return details


def pr_comment_link_to_check(
    full_comparison: FullComparisonInfo, check_link: str
) -> str:
    """Generate a GitHub PR comment that summarizes and links to a GitHub Check."""
    comment = ""

    if full_comparison.benchmarks_with_errors:
        pluralizer = _Pluralizer(full_comparison.benchmarks_with_errors)
        were = pluralizer.were
        s = pluralizer.s
        comment += _clean(
            f"""
            There {were} {len(full_comparison.benchmarks_with_errors)} benchmark
            result{s} with an error:
            """
        )
        comment += _list_results(full_comparison.benchmarks_with_errors, limit=2)

    if full_comparison.no_baseline_runs:
        comment += _clean(
            """
            There weren't enough matching historic benchmark runs to make a call on
            whether there were regressions.
            """
        )
        comment += "\n\n"
    elif full_comparison.benchmarks_with_z_regressions:
        pluralizer = _Pluralizer(full_comparison.benchmarks_with_z_regressions)
        were = pluralizer.were
        s = pluralizer.s
        comment += _clean(
            f"""
            There {were} {len(full_comparison.benchmarks_with_z_regressions)} benchmark
            result{s} indicating a performance regression:
            """
        )
        comment += _list_results(full_comparison.benchmarks_with_z_regressions, limit=2)
    else:
        comment += _clean(
            """
            There were no benchmark performance regressions. 🎉
            """
        )
        comment += "\n\n"

    comment += _clean(
        f"""
        The [full Conbench report]({check_link}) for commit
        `{full_comparison.commit_hash[:8]}` has more details.
        """
    )

    return comment
