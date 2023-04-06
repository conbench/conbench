import collections
import logging
from typing import List

import flask as f

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._comparator import BenchmarkComparator, BenchmarkListComparator
from ..entities._entity import NotFound
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import Commit
from ..entities.compare import CompareBenchmarkResultSerializer
from ..entities.history import set_z_scores
from ..hacks import set_display_benchmark_name, set_display_case_permutation

log = logging.getLogger(__name__)


def _result_dict_for_compare_api(benchmark_result: BenchmarkResult):
    """
    Return a dictionary representing a benchmark result, but for the compare
    API, i.e. this is a minimal/special representation of a benchmark result.
    """
    return {
        "id": benchmark_result.id,
        "batch_id": benchmark_result.batch_id,
        "run_id": benchmark_result.run_id,
        "case_id": benchmark_result.case_id,
        "context_id": benchmark_result.context_id,
        "value": benchmark_result.mean,
        "error": benchmark_result.error,
        "unit": benchmark_result.unit,
        # TODO: change this property name to reflect the idea of 'case permutation'
        "benchmark": benchmark_result.display_case_perm,
        # TODO: change this property name to reflect the idea of 'benchmark name'
        "batch": benchmark_result.display_bmname,
        "language": benchmark_result.context.tags.get("benchmark_language", "unknown"),
        "tags": benchmark_result.case.tags,
        "z_score": benchmark_result.z_score,
    }


def _get_pairs(baseline_items, contender_items):
    """
    TODO: needs concise docstring defining the goals/task of this function.

    You should be able to compare any run with any other run, so we can't
    just key by case_id/context_id/hardware_hash, or you couldn't compare runs
    done on different machine, nor could you compare runs done in different
    contexts.

    Assumptions:
        - A run contains exactly one machine.
        - You are only ever comparing 2 runs or batches.
    """
    pairs = {}
    baseline_items = _dedup_items(baseline_items)
    contender_items = _dedup_items(contender_items)
    baseline_counter = collections.Counter([i["case_id"] for i in baseline_items])
    contender_counter = collections.Counter([i["case_id"] for i in contender_items])
    for item in baseline_items:
        case_id = item["case_id"]
        simple = _simple_key(baseline_counter, contender_counter, case_id)
        _add_pair(pairs, item, "baseline", simple)
    for item in contender_items:
        case_id = item["case_id"]
        simple = _simple_key(baseline_counter, contender_counter, case_id)
        _add_pair(pairs, item, "contender", simple)
    return pairs


def _simple_key(baseline_counter, contender_counter, case_id):
    return baseline_counter[case_id] == 1 and contender_counter[case_id] == 1


def _dedup_items(items):
    filtered = {}
    for item in items:
        filtered[f'{item["case_id"]}-{item["context_id"]}'] = item
    return filtered.values()


def _add_pair(pairs, item, kind, simple):
    case_id, context_id = item["case_id"], item["context_id"]
    key = case_id if simple else f"{case_id}-{context_id}"
    if key not in pairs:
        pairs[key] = {"baseline": None, "contender": None}
    pairs[key][kind] = item


class CompareMixin:
    def _parse_two_ids_or_abort(self, compare_ids):
        if "..." not in compare_ids:
            f.abort(
                404, description="last URL path segment must be of pattern <id>...<id>"
            )

        # I think these can be either two run IDs, two batch IDs or two
        # benchmark result IDs?
        baseline_id, contender_id = compare_ids.split("...", 1)

        if not baseline_id:
            f.abort(404, description="empty baseline ID")

        if not contender_id:
            f.abort(404, description="empty contender ID")

        return baseline_id, contender_id

    def get_query_args_from_request(self):
        """
        Attempt to read a specific set of query parameters from request
        context.
        """
        # what is raw supposed to do?
        raw = f.request.args.get("raw", "false").lower() in ["true", "1"]

        threshold = f.request.args.get("threshold")
        if threshold is not None:
            threshold = float(threshold)

        threshold_z = f.request.args.get("threshold_z")
        if threshold_z is not None:
            threshold_z = float(threshold_z)

        # I think this expression can never raise ValueError.
        # The goal here was probably to raise ValueError?
        # try:
        #     baseline_id, contender_id = compare_ids.split("...", 1)
        # except ValueError:
        #     self.abort_404_not_found()

        return raw, threshold, threshold_z


class CompareEntityEndpoint(ApiEndpoint, CompareMixin):
    def _get_results(self, rid: str) -> List[BenchmarkResult]:
        raise NotImplementedError

    @maybe_login_required
    def get(self, compare_ids) -> f.Response:
        """
        ---
        description: Compare benchmark results.
        responses:
            "200": "CompareEntity"
            "401": "401"
            "404": "404"
        parameters:
          - name: compare_ids
            in: path
            schema:
                type: string
            example: <baseline_id>...<contender_id>
          - in: query
            name: raw
            schema:
              type: boolean
          - in: query
            name: threshold
            schema:
              type: number
          - in: query
            name: threshold_z
            schema:
              type: number
        tags:
          - Comparisons
        """

        baseline_id, contender_id = self._parse_two_ids_or_abort(compare_ids)

        args = self.get_query_args_from_request()
        raw, threshold, threshold_z = args

        baseline_benchmark_result = self._get_results(baseline_id)[0]
        contender_benchmark_result = self._get_results(contender_id)[0]

        set_z_scores(
            contender_benchmark_results=[contender_benchmark_result],
            baseline_commit=baseline_benchmark_result.run.commit,
        )

        # TODO: remove baseline-z-score-related keys from this endpoint
        baseline_benchmark_result.z_score = None

        set_display_case_permutation(baseline_benchmark_result)
        set_display_case_permutation(contender_benchmark_result)
        set_display_benchmark_name(baseline_benchmark_result)
        set_display_benchmark_name(contender_benchmark_result)

        baseline = _result_dict_for_compare_api(baseline_benchmark_result)
        contender = _result_dict_for_compare_api(contender_benchmark_result)
        comparator = BenchmarkComparator(
            baseline,
            contender,
            threshold,
            threshold_z,
        )

        return comparator.compare() if raw else comparator.formatted()


class CompareListEndpoint(ApiEndpoint, CompareMixin):
    def _get_results(self, id: str) -> List[BenchmarkResult]:
        raise NotImplementedError

    @maybe_login_required
    def get(self, compare_ids) -> f.Response:
        """
        ---
        description: Compare benchmark results.
        responses:
            "200": "CompareList"
            "401": "401"
            "404": "404"
        parameters:
          - name: compare_ids
            in: path
            schema:
                type: string
            example: <baseline_id>...<contender_id>
          - in: query
            name: raw
            schema:
              type: boolean
          - in: query
            name: threshold
            schema:
              type: number
          - in: query
            name: threshold_z
            schema:
              type: number
        tags:
          - Comparisons
        """
        # The `baseline_id`` and `contender_id`` may be of various kinds (run
        # ids, batch ids, .... see sub classes below.).

        baseline_id, contender_id = self._parse_two_ids_or_abort(compare_ids)
        raw, threshold, threshold_z = self.get_query_args_from_request()
        baseline_results = self._get_results(baseline_id)
        contender_results = self._get_results(contender_id)

        set_z_scores(
            contender_benchmark_results=contender_results,
            baseline_commit=baseline_results[0].run.commit,
        )

        # TODO: remove baseline-z-score-related keys from this endpoint
        for res in baseline_results:
            res.z_score = None

        baseline_items, contender_items = [], []

        for benchmark_result in baseline_results:
            # TODO: define dynamic properties on BenchmarkResult instead of
            # mutating these objects here in-place.
            set_display_benchmark_name(benchmark_result)
            set_display_case_permutation(benchmark_result)

            baseline_items.append(_result_dict_for_compare_api(benchmark_result))

        for benchmark_result in contender_results:
            set_display_benchmark_name(benchmark_result)
            set_display_case_permutation(benchmark_result)
            contender_items.append(_result_dict_for_compare_api(benchmark_result))

        pairs = _get_pairs(baseline_items, contender_items)

        comparator = BenchmarkListComparator(
            pairs,
            threshold,
            threshold_z,
        )

        result = comparator.compare() if raw else comparator.formatted()
        return f.jsonify(list(result))


class CompareBenchmarksAPI(CompareEntityEndpoint):
    def _get_results(self, benchmark_id) -> List[BenchmarkResult]:
        try:
            benchmark_result = BenchmarkResult.one(id=benchmark_id)
        except NotFound:
            f.abort(
                404, description="no benchmark result found with ID: '{benchmark_id}'"
            )
        return [benchmark_result]


class CompareBatchesAPI(CompareListEndpoint):
    def _get_results(self, batch_id) -> List[BenchmarkResult]:
        benchmark_results = BenchmarkResult.all(batch_id=batch_id)

        if not benchmark_results:
            f.abort(
                404,
                description=f"no benchmark results found for batch ID: '{batch_id}'",
            )
        return benchmark_results


class CompareRunsAPI(CompareListEndpoint):
    def _get_results(self, run_id) -> List[BenchmarkResult]:
        benchmark_results = BenchmarkResult.all(run_id=run_id)
        if not benchmark_results:
            f.abort(
                404, description=f"no benchmark results found for run ID: '{run_id}'"
            )
        return benchmark_results


class CompareCommitsAPI(CompareListEndpoint):
    serializer = CompareBenchmarkResultSerializer()

    @maybe_login_required
    def get(self, compare_shas):
        """
        ---
        description: Compare benchmark results.
        responses:
            "200": "CompareBenchmarkResult"
            "401": "401"
            "404": "404"
        parameters:
          - name: compare_shas
            in: path
            schema:
                type: string
            example: <baseline_sha>...<contender_sha>
        tags:
          - Comparisons
        """
        try:
            baseline_sha, contender_sha = compare_shas.split("...", 1)
        except ValueError:
            # Note(JP): this cannot raise ValueError.
            self.abort_404_not_found()

        baseline_commit = self._get(baseline_sha)
        contender_commit = self._get(contender_sha)
        return self.serializer.one.dump([baseline_commit, contender_commit])

    def _get(self, sha):
        try:
            commit = Commit.one(sha=sha)
        except NotFound:
            f.abort(404, description=f"commit hash not found: {sha}")

        return commit


compare_benchmarks_view = CompareBenchmarksAPI.as_view("compare-benchmarks")
compare_batches_view = CompareBatchesAPI.as_view("compare-batches")
compare_runs_view = CompareRunsAPI.as_view("compare-runs")
compare_commits_view = CompareCommitsAPI.as_view("compare-commits")

rule(
    "/compare/benchmarks/<compare_ids>/",
    view_func=compare_benchmarks_view,
    methods=["GET"],
)
rule(
    "/compare/batches/<compare_ids>/",
    view_func=compare_batches_view,
    methods=["GET"],
)
rule(
    "/compare/runs/<compare_ids>/",
    view_func=compare_runs_view,
    methods=["GET"],
)
rule(
    "/compare/commits/<compare_shas>/",
    view_func=compare_commits_view,
    methods=["GET"],
)
