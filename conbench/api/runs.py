import dataclasses
import functools
from typing import Dict, Optional, Sequence, Set

import flask as f
import sqlalchemy as s

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..dbsession import current_session
from ..entities._entity import EntitySerializer
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import CantFindAncestorCommitsError, Commit, CommitSerializer
from ..entities.hardware import HardwareSerializer
from ..types import THistFingerprint
from ..util import short_commit_msg, tznaive_dt_to_aware_iso8601_for_api


@dataclasses.dataclass
class RunAggregate:
    """Aggregated information about a run."""

    earliest_result: BenchmarkResult
    result_count: int
    any_result_failed: bool

    def update(self, new_result: BenchmarkResult):
        """Update the aggregate information based on a new result."""
        self.earliest_result = (
            new_result
            if new_result.timestamp < self.earliest_result.timestamp
            else self.earliest_result
        )
        self.result_count += 1
        self.any_result_failed = self.any_result_failed or new_result.is_failed

    @functools.cached_property
    def display_commit_time(self) -> str:
        # Note(JP): this is not the commit time
        return self.earliest_result.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

    @functools.cached_property
    def display_commit_msg(self) -> str:
        return short_commit_msg(
            self.earliest_result.commit.message if self.earliest_result.commit else ""
        )


@dataclasses.dataclass
class _CandidateBaselineSearchResult:
    """Information about the search for a candidate baseline run, and the result of the
    search.
    """

    # An error message, if the search failed.
    error: Optional[str] = None

    # The run ID of the candidate baseline run, if the search succeeded.
    baseline_run_id: Optional[str] = None

    # The commit hashes that were skipped during the search, if the search succeeded.
    commits_skipped: Optional[Sequence[str]] = None

    def _dict_for_api_json(self) -> dict:
        return dataclasses.asdict(self)


def _search_for_baseline_run(
    contender_run_id: str,
    contender_run_reason: Optional[str],
    contender_history_fingerprints: Set[THistFingerprint],
    baseline_commit: Optional[Commit],
    commit_limit: int = 20,
) -> _CandidateBaselineSearchResult:
    """Search for and return information about a baseline run of a contender run, where
    the baseline run:

    - is on the given baseline_commit (but not the same run), or in its git ancestry (up
        to ``commit_limit`` commits ago)
    - has a BenchmarkResult with the history fingerprint of any of the contender
        run's BenchmarkResults

    Always returns a _CandidateBaselineSearchResult, and if there are no matches for
    some reason, that reason will be in its ``error`` attribute. If there are multiple
    matches, prefer a baseline run with the same reason as the contender run, and then
    use the baseline run with the most-recent commit, finally tiebreaking by choosing
    the baseline run with the latest BenchmarkResult.timestamp.
    """
    from ..entities.benchmark_result import BenchmarkResult

    if not baseline_commit:
        return _CandidateBaselineSearchResult(
            error="this baseline commit type does not exist for this run"
        )

    try:
        commit_query = baseline_commit.commit_ancestry_query.order_by(
            s.desc("commit_order")
        ).limit(commit_limit)
    except CantFindAncestorCommitsError as e:
        return _CandidateBaselineSearchResult(
            error=f"could not find the baseline commit's ancestry because {e}"
        )

    commits = commit_query.all()
    commit_ids = [commit.ancestor_id for commit in commits]
    commit_hashes = [commit.ancestor_hash for commit in commits]
    earliest_commit_timestamp = commits[-1].ancestor_timestamp

    baseline_run_query = (
        s.select(BenchmarkResult.run_id, BenchmarkResult.commit_id)
        .select_from(BenchmarkResult)
        .join(Commit, Commit.id == BenchmarkResult.commit_id)
        .filter(
            BenchmarkResult.history_fingerprint.in_(contender_history_fingerprints),
            BenchmarkResult.run_id != contender_run_id,
            BenchmarkResult.commit_id.in_(commit_ids),
            BenchmarkResult.timestamp >= earliest_commit_timestamp,  # a nice speedup
        )
        .order_by(
            # Prefer this Run's run_reason,
            s.desc(BenchmarkResult.run_reason == contender_run_reason),
            # then latest commit,
            s.desc(Commit.sha != Commit.fork_point_sha),
            Commit.timestamp.desc(),
            # then latest BenchmarkResult timestamp
            BenchmarkResult.timestamp.desc(),
        )
        .limit(1)
    )
    matching_benchmark_result = current_session.execute(baseline_run_query).first()

    if not matching_benchmark_result:
        return _CandidateBaselineSearchResult(
            error="no matching baseline run was found"
        )

    # Figure out a list of commits that were skipped in the search for a baseline
    index_of_baseline = commit_ids.index(matching_benchmark_result.commit_id)
    commits_skipped = commit_hashes[:index_of_baseline]

    return _CandidateBaselineSearchResult(
        baseline_run_id=matching_benchmark_result.run_id,
        commits_skipped=commits_skipped,
    )


def _get_history_fingerprints_for_run(run_id: str) -> Set[THistFingerprint]:
    return set(
        current_session.scalars(
            s.select(BenchmarkResult.history_fingerprint).filter(
                BenchmarkResult.run_id == run_id
            )
        ).all()
    )


def get_candidate_baseline_runs(
    contender_benchmark_result: "BenchmarkResult",
) -> Dict[str, dict]:
    """Given a benchmark result from a contender run, return information about a few
    different candidate baseline runs, including on the parent commit, fork-point
    commit, and head-of-default-branch commit.

    See docstring of _search_for_baseline_run() for how these are found.
    """
    contender_commit = contender_benchmark_result.commit
    contender_history_fingerprints = set()  # to be cached and reused in this function
    candidates: Dict[str, _CandidateBaselineSearchResult] = {}

    # The direct, single parent in the git graph
    if not contender_commit:
        candidates["parent"] = _CandidateBaselineSearchResult(
            error="the contender run is not connected to the git graph"
        )
    else:
        contender_history_fingerprints = _get_history_fingerprints_for_run(
            contender_benchmark_result.run_id
        )
        candidates["parent"] = _search_for_baseline_run(
            baseline_commit=contender_commit.get_parent_commit(),
            contender_run_id=contender_benchmark_result.run_id,
            contender_run_reason=contender_benchmark_result.run_reason,
            contender_history_fingerprints=contender_history_fingerprints,
        )

    # If this is a PR run, the PR's fork point commit on the default branch
    if not contender_commit:
        candidates["fork_point"] = _CandidateBaselineSearchResult(
            error="the contender run is not connected to the git graph"
        )
    elif contender_commit.sha == contender_commit.fork_point_sha:
        candidates["fork_point"] = _CandidateBaselineSearchResult(
            error="the contender run is already on the default branch"
        )
    else:
        if not contender_history_fingerprints:
            contender_history_fingerprints = _get_history_fingerprints_for_run(
                contender_benchmark_result.run_id
            )
        candidates["fork_point"] = _search_for_baseline_run(
            baseline_commit=contender_commit.get_fork_point_commit(),
            contender_run_id=contender_benchmark_result.run_id,
            contender_run_reason=contender_benchmark_result.run_reason,
            contender_history_fingerprints=contender_history_fingerprints,
        )

    # The latest commit on the default branch that Conbench knows about
    query = (
        s.select(Commit)
        .filter(
            Commit.sha == Commit.fork_point_sha,
            Commit.repository == contender_benchmark_result.commit_repo_url,
        )
        .order_by(s.desc(Commit.timestamp))
        .limit(1)
    )

    latest_commit = current_session.scalars(query).first()
    if not contender_history_fingerprints:
        contender_history_fingerprints = _get_history_fingerprints_for_run(
            contender_benchmark_result.run_id
        )
    candidates["latest_default"] = _search_for_baseline_run(
        baseline_commit=latest_commit,
        contender_run_id=contender_benchmark_result.run_id,
        contender_run_reason=contender_benchmark_result.run_reason,
        contender_history_fingerprints=contender_history_fingerprints,
    )

    return {
        candidate_type: candidate._dict_for_api_json()
        for candidate_type, candidate in candidates.items()
    }


class _Serializer(EntitySerializer):
    def _dump(
        self, benchmark_result: "BenchmarkResult", get_baseline_runs: bool = False
    ):
        if benchmark_result.commit:
            commit_dict = CommitSerializer().one.dump(benchmark_result.commit)
            commit_dict.pop("links", None)
        else:
            commit_dict = None

        hardware_dict = HardwareSerializer().one.dump(benchmark_result.hardware)
        hardware_dict.pop("links", None)
        out_dict = {
            "id": benchmark_result.run_id,
            "tags": benchmark_result.run_tags,
            "reason": benchmark_result.run_reason,
            "timestamp": tznaive_dt_to_aware_iso8601_for_api(
                benchmark_result.timestamp
            ),
            "commit": commit_dict,
            "hardware": hardware_dict,
        }
        if get_baseline_runs:
            out_dict["candidate_baseline_runs"] = get_candidate_baseline_runs(
                benchmark_result
            )
        return out_dict


class RunSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


class RunEntityAPI(ApiEndpoint):
    serializer = RunSerializer()

    @maybe_login_required
    def get(self, run_id):
        """
        ---
        description: |
            Get a run and information about its candidate baseline runs.

            The `"candidate_baseline_runs"` key in the response contains information
            about up to three candidate baseline runs. Each baseline run corresponds to
            a different candidate baseline commit, detailed below. If a baseline run is
            not found for that commit, the response will detail why in the `"error"`
            key. If a baseline run is found, its ID will be returned in the
            `"baseline_run_id"` key.

            The three candidate baseline commits are:

            - the parent commit of the contender run's commit (`"parent"`)
            - if the contender run is on a PR branch, the default-branch commit that the
              PR branch forked from (`"fork_point"`)
            - if the contender run is on a PR branch, the latest commit on the default
              branch that has benchmark results (`"latest_default"`)

            When searching for a baseline run, each matching baseline run must:

            - be on the respective baseline commit, or in its git ancestry
            - match the contender run's hardware
            - have a benchmark result with the `case_id`/`context_id` of any of the
              contender run's benchmark results

            If there are multiple matches, prefer a baseline run with the same reason as
            the contender run, and then use the baseline run with the most-recent
            commit, finally tiebreaking by choosing the baseline run with the latest run
            timestamp.

            If any commits in the git ancestry were skipped to find a matching baseline
            run, those commit hashes will be returned in the `"commits_skipped"` key.
        responses:
            "200": "RunEntityWithBaselines"
            "401": "401"
            "404": "404"
        parameters:
          - name: run_id
            in: path
            schema:
                type: string
        tags:
          - Runs
        """
        any_result = BenchmarkResult.first(run_id=run_id)
        if not any_result:
            self.abort_404_not_found()
        return self.serializer.one._dump(any_result, get_baseline_runs=True)


class RunListAPI(ApiEndpoint):
    serializer = RunSerializer()

    @maybe_login_required
    def get(self):
        """
        ---
        description: |
            Get a list of runs associated with a commit hash or hashes.

            This endpoint implements pagination; see the `cursor` and `page_size` query
            parameters for how it works.
        responses:
            "200": "RunList"
            "401": "401"
        parameters:
          - in: query
            name: commit_hash
            schema:
              type: string
            description: |
                Required. A commit hash or a comma-separated list of commit hashes.
          - in: query
            name: cursor
            schema:
              type: string
              nullable: true
            description: |
                A cursor for pagination through matching runs in alphabetical order by
                `run_id`.

                To get the first page of runs, leave out this query parameter or submit
                `null`. The response's `metadata` key will contain a `next_page_cursor`
                key, which will contain the cursor to provide to this query parameter in
                order to get the next page. (If there is expected to be no data in the
                next page, the `next_page_cursor` will be `null`.)

                The first page will contain the `page_size` runs associated with the
                given commit hash(es) that are first alphabetically by `run_id`. Each
                subsequent page will have up to `page_size` runs, continuing
                alphabetically, until there are no more matching runs.

                Implementation detail: currently, the next page's cursor value is equal
                to the latest `run_id` alphabetically in the current page. A page of
                runs is therefore defined as the `page_size` matching runs with an ID
                alphabetically later than the given cursor value.

                Note that this means that if a run is created DURING a client's request
                loop with an ID that is alphabetically earlier than the cursor value, it
                will not be included in the next page. This is a known limitation of the
                current implementation, and it is not expected to be a problem in
                practice. This is because the number of runs per commit hash is expected
                to be much less than the page size, and runs are added quite
                infrequently.
          - in: query
            name: page_size
            schema:
              type: integer
              minimum: 1
              maximum: 1000
            description: |
                The size of pages for pagination (see `cursor`). Default 100. Max 1000.
        tags:
          - Runs
        """
        filters = []

        commit_hash_arg: Optional[str] = f.request.args.get("commit_hash")
        if not commit_hash_arg:
            self.abort_400_bad_request("commit_hash is required")
        filters.append(Commit.sha.in_(commit_hash_arg.split(",")))

        cursor_arg: Optional[str] = f.request.args.get("cursor")
        if cursor_arg and cursor_arg != "null":
            filters.append(BenchmarkResult.run_id > cursor_arg)

        page_size_arg = f.request.args.get("page_size", 100)
        try:
            page_size = int(page_size_arg)
            assert 1 <= page_size <= 1000
        except Exception:
            self.abort_400_bad_request(
                "page_size must be a positive integer no greater than 1000"
            )

        query = (
            s.select(BenchmarkResult)
            .join(Commit)
            .where(*filters)
            .distinct(BenchmarkResult.run_id)
            .order_by(BenchmarkResult.run_id)
            .limit(page_size)
        )

        data = [
            self.serializer.one._dump(result, get_baseline_runs=False)
            for result in current_session.scalars(query).all()
        ]

        if len(data) == page_size:
            next_page_cursor = data[-1]["id"]
            # There's an edge case here where the last page happens to have exactly
            # page_size runs. So the client will grab one more (empty) page. The
            # alternative would be to query the DB here, every single time, to *make
            # sure* the next page will contain runs... but that feels very expensive.
        else:
            # If there were fewer than page_size runs, the next page should be empty
            next_page_cursor = None

        return {
            "data": data,
            "metadata": {"next_page_cursor": next_page_cursor},
        }


run_entity_view = RunEntityAPI.as_view("run")
run_list_view = RunListAPI.as_view("runs")

rule(
    "/runs/",
    view_func=run_list_view,
    methods=["GET"],
)
rule(
    "/runs/<run_id>/",
    view_func=run_entity_view,
    methods=["GET"],
)
