"""Message formatting helpers for alerts."""

import textwrap
from typing import List, Optional

from .conbench_dataclasses import BenchmarkResultInfo, FullComparisonInfo
from .integrations.github import CheckStatus


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


def _run_bullet(reason: str, time: str, link: str, hardware: str) -> str:
    return f"- {reason.title()} Run on `{hardware}` at [{time}]({link})"


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
                benchmark_result.run_hardware,
            )
            previous_run_id = benchmark_result.run_id
        out += f"\n  - [{benchmark_result.display_name}]({benchmark_result.link})"

    if out:
        out += "\n\n"

    return out


def _all_runs(full_comparison: FullComparisonInfo) -> str:
    """Create a Markdown list of all runs analyzed."""
    out = "## All benchmark runs analyzed:\n"
    for comparison in full_comparison.run_comparisons:
        out += "\n"
        out += _run_bullet(
            comparison.contender_reason,
            comparison.contender_datetime,
            comparison.contender_link,
            comparison.contender_hardware_name,
        )
    return out


class Alerter:
    """A class to generate default messages and statuses for alerting. You can override
    any methods for your project's custom settings.
    """

    @staticmethod
    def clean(text: str) -> str:
        """A small helper: clean block text so it displays nicely as GitHub Markdown."""
        return textwrap.fill(textwrap.dedent(text), 10000).replace("  ", "\n\n").strip()

    def intro_sentence(self, full_comparison: FullComparisonInfo) -> str:
        """Generate a Markdown sentence to introduce a message."""
        s = _Pluralizer(full_comparison.run_comparisons).s
        if full_comparison.commit_hash:
            intro = self.clean(
                f"""
                Conbench analyzed the {len(full_comparison.run_comparisons)} benchmark
                run{s} on commit `{full_comparison.commit_hash[:8]}`.
                """
            )
        else:
            intro = self.clean(
                f"""
                Conbench analyzed the {len(full_comparison.run_comparisons)} benchmark
                run{s} that triggered this notification.
                """
            )
        return intro + "\n\n"

    def github_check_status(self, full_comparison: FullComparisonInfo) -> CheckStatus:
        """Return a different status based on errors and regressions."""
        if full_comparison.results_with_errors:
            # results with errors require action
            return CheckStatus.ACTION_REQUIRED
        elif full_comparison.results_with_z_regressions:
            # no errors, but results with regressions are still a failure
            return CheckStatus.FAILURE
        elif full_comparison.has_any_z_analyses:
            # we analyzed z-scores and didn't find errors or regressions
            return CheckStatus.SUCCESS
        elif full_comparison.has_any_contender_results:
            # we have results but couldn't analyze z-scores
            # (normal at beginning of history)
            return CheckStatus.SKIPPED
        else:
            # we don't have results; this requires action
            return CheckStatus.ACTION_REQUIRED

    def github_check_title(self, full_comparison: FullComparisonInfo) -> str:
        if full_comparison.results_with_errors:
            return "Some benchmarks had errors"
        elif not full_comparison.has_any_z_analyses:
            return "Could not do the lookback z-score analysis"
        else:
            pluralizer = _Pluralizer(full_comparison.results_with_z_regressions)
            s = pluralizer.s
            return (
                f"Found {len(full_comparison.results_with_z_regressions)} regression{s}"
            )

    def github_check_summary(
        self, full_comparison: FullComparisonInfo, build_url: Optional[str]
    ) -> str:
        """Generate a Markdown summary of what happened regarding errors and
        regressions.
        """
        summary = self.intro_sentence(full_comparison)

        if not full_comparison.has_any_contender_runs:
            summary += self.clean(
                """
                None of the specified runs were found on the Conbench server.
                """
            )
            if build_url:
                summary += f" See the [build logs]({build_url}) for more information."
            # exit early
            return summary

        if not full_comparison.has_any_contender_results:
            summary += self.clean(
                """
                None of the specified runs had any associated benchmark results.
                """
            )
            if build_url:
                summary += f" See the [build logs]({build_url}) for more information."
            # exit early
            return summary + "\n\n" + _all_runs(full_comparison)

        if full_comparison.results_with_errors:
            summary += self.clean(
                """
                ## Benchmarks with errors

                These are errors that were caught while running the benchmarks. You can
                click each link to go to the Conbench entry for that benchmark, which
                might have more information about what the error was.
                """
            )
            summary += _list_results(full_comparison.results_with_errors)

        summary += "## Benchmarks with performance regressions\n\n"

        if not full_comparison.has_any_z_analyses:
            summary += self.clean(
                """
                There weren't enough matching historic runs in Conbench to make a call
                on whether there were regressions or not.

                To use the lookback z-score method of determining regressions, there
                need to be at least two historic runs on the default branch which, when
                compared to one of the runs on the contender commit, are on the same
                hardware, and have at least one of the same benchmark case and context
                pairs.
                """
            )
            # exit early
            return summary + "\n\n" + _all_runs(full_comparison)

        pluralizer = _Pluralizer(full_comparison.results_with_z_regressions)
        were = pluralizer.were
        s = pluralizer.s
        summary += self.clean(
            f"""
            There {were} {len(full_comparison.results_with_z_regressions)} possible
            performance regression{s}, according to the lookback z-score method.
            """
        )
        summary += "\n\n"

        if full_comparison.results_with_z_regressions:
            summary += "### Benchmarks with regressions:"
            summary += _list_results(full_comparison.results_with_z_regressions)

        return summary + _all_runs(full_comparison)

    def github_check_details(
        self, full_comparison: FullComparisonInfo
    ) -> Optional[str]:
        """Generate Markdown details of what happened regarding regressions."""
        details = ""

        if not full_comparison.commit_hash:
            details += self.clean(
                """
                This report was not associated with any commit connected to the git
                graph. This probably means that benchmarks were run on a transient
                merge-commit.
                """
            )
            details += "\n\n"

        if full_comparison.has_any_z_analyses:
            details += self.clean(
                f"""
                This report was generated using the lookback z-score method with a
                z-score threshold of {full_comparison.z_score_threshold}.
                """
            )

        return details or None

    def github_pr_comment(
        self, full_comparison: FullComparisonInfo, check_link: str
    ) -> str:
        """Generate a GitHub PR comment that summarizes and links to a GitHub Check."""
        comment = self.intro_sentence(full_comparison)

        if not full_comparison.has_any_contender_runs:
            comment += self.clean(
                """
                None of the specified runs were found on the Conbench server.
                """
            )
            comment += "\n\n"
        elif not full_comparison.has_any_contender_results:
            comment += self.clean(
                """
                None of the specified runs had any associated benchmark results.
                """
            )
            comment += "\n\n"
        else:
            if full_comparison.results_with_errors:
                pluralizer = _Pluralizer(full_comparison.results_with_errors)
                were = pluralizer.were
                s = pluralizer.s
                comment += self.clean(
                    f"""
                    There {were} {len(full_comparison.results_with_errors)} benchmark
                    result{s} with an error:
                    """
                )
                comment += _list_results(full_comparison.results_with_errors, limit=2)

            if not full_comparison.has_any_z_analyses:
                comment += self.clean(
                    """
                    There weren't enough matching historic benchmark results to make a
                    call on whether there were regressions.
                    """
                )
                comment += "\n\n"
            elif full_comparison.results_with_z_regressions:
                pluralizer = _Pluralizer(full_comparison.results_with_z_regressions)
                were = pluralizer.were
                s = pluralizer.s
                comment += self.clean(
                    f"""
                    There {were} {len(full_comparison.results_with_z_regressions)}
                    benchmark result{s} indicating a performance regression:
                    """
                )
                comment += _list_results(
                    full_comparison.results_with_z_regressions, limit=2
                )
            else:
                comment += self.clean(
                    """
                    There were no benchmark performance regressions. 🎉
                    """
                )
                comment += "\n\n"

        comment += self.clean(
            f"""
            The [full Conbench report]({check_link}) has more details.
            """
        )

        return comment

    def slack_message(
        self,
        full_comparison: FullComparisonInfo,
        check_details: dict,
        comment_details: Optional[dict],
    ) -> str:
        """Generate a Slack message that links to a GitHub Check."""
        status = self.github_check_status(full_comparison)
        link = check_details["html_url"]
        message = f"Check run posted with status `{status.value}`: <{link}|check link>"
        if comment_details:
            message += f", <{comment_details['html_url']}|comment link>"

        return message
