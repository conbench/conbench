import collections

import flask as f

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._comparator import BenchmarkComparator, BenchmarkListComparator
from ..entities._entity import NotFound
from ..entities.commit import Commit
from ..entities.compare import CompareSummarySerializer
from ..entities.distribution import set_z_scores
from ..entities.summary import Summary
from ..hacks import set_display_batch, set_display_name


def _compare_entity(summary):
    return {
        "id": summary.id,
        "batch_id": summary.batch_id,
        "run_id": summary.run_id,
        "case_id": summary.case_id,
        "context_id": summary.context_id,
        "value": summary.mean,
        "unit": summary.unit,
        "benchmark": summary.display_name,
        "batch": summary.display_batch,
        "language": summary.context.tags.get("benchmark_language", "unknown"),
        "tags": summary.case.tags,
        "z_score": summary.z_score,
    }


def _get_pairs(baseline_items, contender_items):
    """
    You should be able to compare any run with any other run, so we can't
    just key by case_id/context_id/machine_hash, or you couldn't compare runs
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
    def get_args(self, compare_ids):
        raw = f.request.args.get("raw", "false").lower() in ["true", "1"]

        threshold = f.request.args.get("threshold")
        if threshold is not None:
            threshold = int(threshold)

        threshold_z = f.request.args.get("threshold_z")
        if threshold_z is not None:
            threshold_z = int(threshold_z)

        try:
            baseline_id, contender_id = compare_ids.split("...", 1)
        except ValueError:
            self.abort_404_not_found()

        return raw, threshold, threshold_z, baseline_id, contender_id


class CompareEntityEndpoint(ApiEndpoint, CompareMixin):
    @maybe_login_required
    def get(self, compare_ids):
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
              type: integer
          - in: query
            name: threshold_z
            schema:
              type: integer
        tags:
          - Comparisons
        """
        args = self.get_args(compare_ids)
        raw, threshold, threshold_z, baseline_id, contender_id = args

        baseline_summary = self._get(baseline_id)
        contender_summary = self._get(contender_id)
        set_display_name(baseline_summary)
        set_display_name(contender_summary)
        set_display_batch(baseline_summary)
        set_display_batch(contender_summary)

        baseline = _compare_entity(baseline_summary)
        contender = _compare_entity(contender_summary)
        comparator = BenchmarkComparator(
            baseline,
            contender,
            threshold,
            threshold_z,
        )

        return comparator.compare() if raw else comparator.formatted()


class CompareListEndpoint(ApiEndpoint, CompareMixin):
    @maybe_login_required
    def get(self, compare_ids):
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
              type: integer
          - in: query
            name: threshold_z
            schema:
              type: integer
        tags:
          - Comparisons
        """
        args = self.get_args(compare_ids)
        raw, threshold, threshold_z, baseline_id, contender_id = args

        baselines = self._get(baseline_id)
        contenders = self._get(contender_id)

        baseline_items, contender_items = [], []
        for summary in baselines:
            set_display_name(summary)
            set_display_batch(summary)
            baseline_items.append(_compare_entity(summary))
        for summary in contenders:
            set_display_name(summary)
            set_display_batch(summary)
            contender_items.append(_compare_entity(summary))

        pairs = _get_pairs(baseline_items, contender_items)
        comparator = BenchmarkListComparator(
            pairs,
            threshold,
            threshold_z,
        )

        result = comparator.compare() if raw else comparator.formatted()
        return f.jsonify(list(result))


class CompareBenchmarksAPI(CompareEntityEndpoint):
    def _get(self, benchmark_id):
        try:
            summary = Summary.one(id=benchmark_id)
        except NotFound:
            self.abort_404_not_found()
        set_z_scores([summary])
        return summary


class CompareBatchesAPI(CompareListEndpoint):
    def _get(self, batch_id):
        summaries = Summary.all(batch_id=batch_id)
        if not summaries:
            self.abort_404_not_found()
        set_z_scores(summaries)
        return summaries


class CompareRunsAPI(CompareListEndpoint):
    def _get(self, run_id):
        summaries = Summary.all(run_id=run_id)
        if not summaries:
            self.abort_404_not_found()
        set_z_scores(summaries)
        return summaries


class CompareCommitsAPI(CompareListEndpoint):
    serializer = CompareSummarySerializer()

    @maybe_login_required
    def get(self, compare_shas):
        """
        ---
        description: Compare benchmark results.
        responses:
            "200": "CompareSummary"
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
            self.abort_404_not_found()
        baseline_commit = self._get(baseline_sha)
        contender_commit = self._get(contender_sha)
        return self.serializer.one.dump([baseline_commit, contender_commit])

    def _get(self, sha):
        try:
            commit = Commit.one(sha=sha)
        except NotFound:
            self.abort_404_not_found()
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
