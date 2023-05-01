"""Dataclasses for organizing and storing relevant info from Conbench."""

from dataclasses import dataclass
from typing import List, Optional

from benchclients.logging import fatal_and_log


@dataclass
class BenchmarkResultInfo:
    """Track and organize specific info about one BenchmarkResult."""

    name: str
    link: str
    has_error: bool
    has_z_regression: bool
    run_id: str
    run_reason: str
    run_time: str
    run_link: str


@dataclass
class RunComparisonInfo:
    """Track and organize specific info about a comparison between a contender run and
    its baseline run.

    Parameters
    ----------
    contender_info
        The dict returned from Conbench when hitting /runs/{contender_run_id}. Contains
        info about the run's ID, commit, errors, links, etc.
    baseline_run_type
        The user-given baseline run type to look for.
    compare_results
        The list returned from Conbench when hitting
        /compare/runs/{baseline_run_id}...{contender_run_id}, only if a baseline run
        exists for this contender run. Contains a comparison for every benchmark result
        to its baseline, including the statistics and regression analysis.
    benchmark_results
        The list returned from Conbench when hitting
        /benchmark-results/?run_id={contender_run_id}, only if the contender run has
        errors and there is no baseline run. Contains info about each benchmark result
        in the contender run, including statistics and tracebacks. Only used when a
        baseline run doesn't exist because otherwise all this information is already in
        the compare_results.
    """

    contender_info: dict
    baseline_run_type: str
    compare_results: Optional[List[dict]] = None
    benchmark_results: Optional[List[dict]] = None

    @property
    def contender_benchmark_result_info(self) -> List[BenchmarkResultInfo]:
        """A clean list of dataclasses corresponding to useful information about each
        benchmark result on the contender run.
        """
        if self.compare_results:
            assert self.compare_link
            return [
                BenchmarkResultInfo(
                    name=comparison["contender"]["case_permutation"],
                    link=self.benchmark_result_link(
                        comparison["contender"]["benchmark_result_id"]
                    ),
                    has_error=bool(comparison["contender"]["error"]),
                    has_z_regression=comparison["analysis"]["lookback_z_score"][
                        "regression_indicated"
                    ]
                    if comparison["analysis"]["lookback_z_score"]
                    else False,
                    run_id=self.contender_id,
                    run_reason=self.contender_reason,
                    run_time=self.contender_datetime,
                    run_link=self.compare_link,
                )
                for comparison in self.compare_results
                if comparison["contender"]
            ]
        elif self.benchmark_results:
            return [
                BenchmarkResultInfo(
                    name=benchmark_result["tags"].get(
                        "name", str(benchmark_result["tags"])
                    ),
                    link=self.benchmark_result_link(benchmark_result["id"]),
                    has_error=bool(benchmark_result["error"]),
                    has_z_regression=False,  # no baseline run
                    run_id=self.contender_id,
                    run_reason=self.contender_reason,
                    run_time=self.contender_datetime,
                    run_link=self.contender_link,
                )
                for benchmark_result in self.benchmark_results
            ]
        else:
            return []

    @property
    def contender_reason(self) -> str:
        """The contender run reason."""
        return self.contender_info["reason"]

    @property
    def contender_datetime(self) -> str:
        """The contender run datetime."""
        dt: str = self.contender_info["timestamp"]
        return dt.replace("T", " ")

    @property
    def contender_link(self) -> str:
        """The link to the contender run page in the webapp."""
        return f"{self.app_url}/runs/{self.contender_id}"

    @property
    def compare_link(self) -> Optional[str]:
        """The link to the run comparison page in the webapp."""
        if self.compare_path:
            # self._compare_path has a leading slash already
            return f"{self.app_url}{self.compare_path}"
        return None

    def benchmark_result_link(self, benchmark_result_id: str) -> str:
        """Get the link to a specific benchmark result in the webapp."""
        return f"{self.app_url}/benchmarks/{benchmark_result_id}"

    @property
    def has_errors(self) -> bool:
        """Whether this run has any benchmark errors."""
        return self.contender_info["has_errors"]

    @property
    def contender_id(self) -> str:
        """The contender run_id."""
        return self.contender_info["id"]

    @property
    def baseline_id(self) -> Optional[str]:
        """The baseline run_id, if found."""
        return self.contender_info["candidate_baseline_runs"][self.baseline_run_type][
            "baseline_run_id"
        ]

    @property
    def baseline_error(self) -> Optional[str]:
        """The error message if Conbench failed to get a baseline run."""
        return self.contender_info["candidate_baseline_runs"][self.baseline_run_type][
            "error"
        ]

    @property
    def baseline_commits_skipped(self) -> Optional[List[str]]:
        """The commit hashes skipped to find the baseline run, if it was found."""
        return self.contender_info["candidate_baseline_runs"][self.baseline_run_type][
            "commits_skipped"
        ]

    @property
    def app_url(self) -> str:
        """The base URL to use for links to the webapp, without a trailing slash."""
        self_link: str = self.contender_info["links"]["self"]
        return self_link.rsplit("/api/", 1)[0]

    @property
    def compare_path(self) -> Optional[str]:
        """The API path to get comparisons between the baseline and contender."""
        if self.baseline_id:
            return f"/compare/runs/{self.baseline_id}...{self.contender_id}/"
        return None


@dataclass
class FullComparisonInfo:
    """Track and organize specific info about ALL the runs on the contender commit and
    the comparisons to their baselines.
    """

    run_comparisons: List[RunComparisonInfo]

    def __post_init__(self):
        # Any code that constructs an instance should ensure run_comparisons is non-empty
        assert self.run_comparisons

    @property
    def benchmarks_with_errors(self) -> List[BenchmarkResultInfo]:
        """Get information about all benchmark results with errors across runs."""
        out = []

        for comparison in self.run_comparisons:
            out += [
                benchmark_result_info
                for benchmark_result_info in comparison.contender_benchmark_result_info
                if benchmark_result_info.has_error
            ]

        return out

    @property
    def benchmarks_with_z_regressions(self) -> List[BenchmarkResultInfo]:
        """Get information about all benchmark results across runs whose z-scores were
        extreme enough to constitute a regression.
        """
        out = []

        for comparison in self.run_comparisons:
            out += [
                benchmark_result_info
                for benchmark_result_info in comparison.contender_benchmark_result_info
                if benchmark_result_info.has_z_regression
            ]

        return out

    @property
    def no_baseline_runs(self) -> bool:
        """Whether all contender runs are missing a baseline run."""
        return not any(
            run_comparison.baseline_id for run_comparison in self.run_comparisons
        )

    @property
    def z_score_threshold(self) -> float:
        """The z-score threshold used in this analysis."""
        z_score_thresholds = set()
        for run_comparison in self.run_comparisons:
            if run_comparison.compare_results:
                for compare in run_comparison.compare_results:
                    if compare["analysis"]["lookback_z_score"]:
                        z_score_thresholds.add(
                            compare["analysis"]["lookback_z_score"]["z_threshold"]
                        )

        if len(z_score_thresholds) != 1:
            fatal_and_log(
                f"There wasn't exactly one z_score_threshold: {z_score_thresholds=}"
            )
        return z_score_thresholds.pop()

    @property
    def commit_hash(self) -> Optional[str]:
        """The contender hash used in this analysis."""
        commit_hashes = set()
        for run_comparison in self.run_comparisons:
            if run_comparison.contender_info["commit"]:
                commit_hashes.add(run_comparison.contender_info["commit"]["sha"])

        if len(commit_hashes) == 0:
            return None
        if len(commit_hashes) != 1:
            fatal_and_log(f"There wasn't exactly one commit_hash: {commit_hashes=}")
        return commit_hashes.pop()

    @property
    def app_url(self) -> str:
        """The base URL to use for links to the webapp, without a trailing slash."""
        return self.run_comparisons[0].app_url
