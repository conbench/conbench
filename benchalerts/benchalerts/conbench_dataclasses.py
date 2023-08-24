"""Dataclasses for organizing and storing relevant info from Conbench."""

from dataclasses import dataclass
from typing import List, Optional

from benchclients.logging import log


@dataclass
class BenchmarkResultInfo:
    """Track and organize specific info about one BenchmarkResult."""

    display_name: str
    link: str
    has_error: bool
    has_z_regression: bool
    run_id: str
    run_reason: str
    run_time: str
    run_hardware: str
    run_link: str


@dataclass
class RunComparisonInfo:
    """Track and organize specific info about a comparison between a contender run and
    its baseline run.

    compare_results and benchmark_results are mutually exclusive.

    Parameters
    ----------
    conbench_api_url
        A URL to the Conbench API, ending in /api.
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
        /benchmark-results/?run_id={contender_run_id}, only if there is no baseline run.
        Contains info about each benchmark result in the contender run, including
        statistics and tracebacks. Only used when a baseline run doesn't exist because
        otherwise all this information is already in the compare_results.
    """

    conbench_api_url: str
    contender_info: dict
    baseline_run_type: str
    compare_results: Optional[List[dict]] = None
    benchmark_results: Optional[List[dict]] = None

    @staticmethod
    def _result_display_name_from_compare_dict(result: dict) -> str:
        """Generate a name for a benchmark result to be displayed in a notification list.

        Given: the compare endpoint's payload's "contender" key dict:
        https://conbench.ursa.dev/api/redoc#tag/Comparisons/paths/~1api~1compare~1benchmark-results~1%7Bcompare_ids%7D~1/get
        """
        display_name = f'`{result["benchmark_name"]}`'
        if result["language"] and result["language"] != "unknown":
            display_name += f' ({result["language"]})'
        if result["case_permutation"] != "no-permutations":
            display_name += f' with {result["case_permutation"]}'
        return display_name

    @property
    def contender_benchmark_result_info(self) -> List[BenchmarkResultInfo]:
        """A clean list of dataclasses corresponding to useful information about each
        benchmark result on the contender run.
        """
        if self.compare_results:
            assert self.run_compare_link
            return [
                BenchmarkResultInfo(
                    display_name=self._result_display_name_from_compare_dict(
                        comparison["contender"]
                    ),
                    link=self.make_benchmark_result_link(
                        contender_result_id=comparison["contender"][
                            "benchmark_result_id"
                        ],
                        baseline_result_id=comparison["baseline"]["benchmark_result_id"]
                        if comparison["baseline"]
                        and not comparison["contender"]["error"]
                        else None,
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
                    run_hardware=self.contender_hardware_name,
                    run_link=self.run_compare_link,
                )
                for comparison in self.compare_results
                if comparison["contender"]
            ]
        elif self.benchmark_results:
            return [
                BenchmarkResultInfo(
                    display_name=benchmark_result["tags"].get(
                        "name", str(benchmark_result["tags"])
                    ),
                    link=self.make_benchmark_result_link(
                        contender_result_id=benchmark_result["id"],
                        baseline_result_id=None,
                    ),
                    has_error=bool(benchmark_result["error"]),
                    has_z_regression=False,  # no baseline run
                    run_id=self.contender_id,
                    run_reason=self.contender_reason,
                    run_time=self.contender_datetime,
                    run_hardware=self.contender_hardware_name,
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
    def contender_hardware_name(self) -> str:
        """The contender run machine."""
        return self.contender_info["hardware"]["name"]

    @property
    def contender_link(self) -> str:
        """The link to the contender run page in the webapp."""
        return f"{self.app_url}/runs/{self.contender_id}"

    @property
    def run_compare_link(self) -> Optional[str]:
        """The link to the run comparison page in the webapp."""
        if self.compare_path:
            # self._compare_path has a leading slash already
            return f"{self.app_url}{self.compare_path}"
        return None

    def make_benchmark_result_link(
        self, contender_result_id: str, baseline_result_id: Optional[str]
    ) -> str:
        """Get the link to a specific benchmark result in the webapp, or to the result
        comparison page if a baseline result ID is given.
        """
        if baseline_result_id:
            return f"{self.app_url}/compare/benchmarks/{baseline_result_id}...{contender_result_id}"
        return f"{self.app_url}/benchmark-results/{contender_result_id}"

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
        return self.conbench_api_url.rsplit("/api", 1)[0]

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

    # Can be empty.
    run_comparisons: List[RunComparisonInfo]

    @property
    def has_any_contender_runs(self) -> bool:
        """Whether there are any contender runs available."""
        return bool(self.run_comparisons)

    @property
    def has_any_contender_results(self) -> bool:
        """Whether there are any contender benchmark results available."""
        for run_comparison in self.run_comparisons:
            if run_comparison.contender_benchmark_result_info:
                return True
        return False

    @property
    def has_any_z_analyses(self) -> bool:
        """Whether there are any lookback z-score analyses available."""
        for run_comparison in self.run_comparisons:
            if run_comparison.compare_results:
                for compare_result in run_comparison.compare_results:
                    if compare_result["analysis"]["lookback_z_score"]:
                        return True
        return False

    @property
    def results_with_errors(self) -> List[BenchmarkResultInfo]:
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
    def results_with_z_regressions(self) -> List[BenchmarkResultInfo]:
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
    def z_score_threshold(self) -> Optional[float]:
        """The z-score threshold used in this analysis."""
        z_score_thresholds = set()
        for run_comparison in self.run_comparisons:
            if run_comparison.compare_results:
                for compare in run_comparison.compare_results:
                    if compare["analysis"]["lookback_z_score"]:
                        z_score_thresholds.add(
                            compare["analysis"]["lookback_z_score"]["z_threshold"]
                        )

        if len(z_score_thresholds) == 0:
            return None
        if len(z_score_thresholds) != 1:
            log.warn(
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
            log.warn(f"There wasn't exactly one commit_hash: {commit_hashes=}")
        return commit_hashes.pop()

    @property
    def app_url(self) -> Optional[str]:
        """The base URL to use for links to the webapp, without a trailing slash."""
        if self.has_any_contender_runs:
            return self.run_comparisons[0].app_url
        return None
