import dataclasses
import logging
import time
from datetime import timezone
from typing import TYPE_CHECKING, Dict, Optional, Sequence, Tuple
from urllib.parse import urlparse

import flask as f
import marshmallow
import sqlalchemy as s

import conbench.util
from conbench.dbsession import current_session

from ..entities._entity import EntitySerializer
from ..entities.commit import (
    CantFindAncestorCommitsError,
    Commit,
    CommitSerializer,
    TypeCommitInfoGitHub,
    backfill_default_branch_commits,
    get_github_commit_metadata,
)
from ..entities.hardware import (
    ClusterSchema,
    Hardware,
    HardwareSerializer,
    MachineSchema,
)

if TYPE_CHECKING:
    from ..entities.benchmark_result import BenchmarkResult

log = logging.getLogger(__name__)


# This is used in two places.
github_commit_info_descr = conbench.util.dedent_rejoin(
    """
    GitHub-flavored commit information.

    Use this object to tell Conbench with which specific state of benchmarked
    code (repository identifier, commit hash) the BenchmarkResult is
    associated.

    This property is optional. If not provided, it means that this benchmark
    result is not associated with any particular state of benchmarked code.

    Not associating a benchmark result with commit information has special,
    limited purpose (pre-merge benchmarks, testing). It generally means that
    this benchmark result will not be considered for time series analysis along
    a commit tree.

    TODO: allow for associating a benchmark result with a repository (URL), w/o
    providing commit information (cf. issue #1165).
    """
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
    contender_run_reason: str,
    contender_hardware_checksum: str,
    baseline_commit: Optional[Commit],
    commit_limit: int = 20,
) -> _CandidateBaselineSearchResult:
    """Search for and return information about a baseline run of a contender run, where
    the baseline run:

    - is on the given baseline_commit, or in its git ancestry (up to
        ``commit_limit`` commits ago)
    - matches the contender run's hardware checksum
    - has a BenchmarkResult with the case_id/context_id of any of the contender
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
        ancestor_commits = (
            baseline_commit.commit_ancestry_query.order_by(s.desc("commit_order"))
            .limit(commit_limit)
            .subquery()
        )
    except CantFindAncestorCommitsError as e:
        return _CandidateBaselineSearchResult(
            error=f"could not find the baseline commit's ancestry because {e}"
        )

    baseline_run_query = (
        s.select(
            BenchmarkResult.run_id,
            Commit.sha,
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
        )
        .select_from(BenchmarkResult)
        .join(Hardware, Hardware.id == BenchmarkResult.hardware_id)
        .join(Commit, Commit.id == BenchmarkResult.commit_id)
        .join(ancestor_commits, ancestor_commits.c.ancestor_id == Commit.id)
        .filter(
            Hardware.hash == contender_hardware_checksum,
            BenchmarkResult.run_id != contender_run_id,
        )
        .order_by(
            # Prefer this Run's run_reason,
            s.desc(BenchmarkResult.run_reason == contender_run_reason),
            ancestor_commits.c.commit_order.desc(),  # then latest commit,
            BenchmarkResult.timestamp.desc(),  # then latest BenchmarkResult timestamp
        )
    )
    matching_benchmark_results = current_session.execute(baseline_run_query).all()

    valid_cases_and_contexts = set(
        row.tuple()
        for row in current_session.execute(
            s.select(BenchmarkResult.case_id, BenchmarkResult.context_id).filter(
                BenchmarkResult.run_id == contender_run_id
            )
        ).all()
    )

    for row in matching_benchmark_results:
        baseline_run_id, baseline_commit_hash, case_id, context_id = row.tuple()
        if (case_id, context_id) in valid_cases_and_contexts:
            # Continue onward with the first one that matches a case_id/context_id
            # of this run
            break
    else:
        return _CandidateBaselineSearchResult(
            error="no matching baseline run was found"
        )

    # Figure out a list of commits that were skipped in the search for a baseline
    commit_hashes_searched = current_session.scalars(
        s.select(Commit.sha)
        .select_from(ancestor_commits)
        .join(Commit, Commit.id == ancestor_commits.c.ancestor_id)
        .order_by(ancestor_commits.c.commit_order.desc())
    ).all()
    index_of_baseline = commit_hashes_searched.index(baseline_commit_hash)
    commits_skipped = commit_hashes_searched[:index_of_baseline]

    return _CandidateBaselineSearchResult(
        baseline_run_id=baseline_run_id, commits_skipped=commits_skipped
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
    candidates: Dict[str, _CandidateBaselineSearchResult] = {}

    # The direct, single parent in the git graph
    if not contender_commit:
        candidates["parent"] = _CandidateBaselineSearchResult(
            error="the contender run is not connected to the git graph"
        )
    else:
        candidates["parent"] = _search_for_baseline_run(
            baseline_commit=contender_commit.get_parent_commit(),
            contender_run_id=contender_benchmark_result.run_id,
            contender_run_reason=contender_benchmark_result.run_reason,
            contender_hardware_checksum=contender_benchmark_result.hardware.hash,
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
        candidates["fork_point"] = _search_for_baseline_run(
            baseline_commit=contender_commit.get_fork_point_commit(),
            contender_run_id=contender_benchmark_result.run_id,
            contender_run_reason=contender_benchmark_result.run_reason,
            contender_hardware_checksum=contender_benchmark_result.hardware.hash,
        )

    # The latest commit on the default branch that Conbench knows about
    query = s.select(Commit).filter(Commit.sha == Commit.fork_point_sha)

    # TODO: how do we filter by repository if there's no commit?
    # (For now we just choose the latest commit of any repository.)
    if contender_commit:
        query = query.filter(Commit.repository == contender_commit.repository)

    latest_commit = current_session.scalars(
        query.order_by(s.desc(Commit.timestamp)).limit(1)
    ).first()
    candidates["latest_default"] = _search_for_baseline_run(
        baseline_commit=latest_commit,
        contender_run_id=contender_benchmark_result.run_id,
        contender_run_reason=contender_benchmark_result.run_reason,
        contender_hardware_checksum=contender_benchmark_result.hardware.hash,
    )

    return {
        candidate_type: candidate._dict_for_api_json()
        for candidate_type, candidate in candidates.items()
    }


def commit_fetch_info_and_create_in_db_if_not_exists(
    ghcommit: TypeCommitInfoGitHub,
) -> Commit:
    """
    Insert new Commit entity into database if required.

    If Commit not yet known in database: fetch data about commit (and related
    commits) from GitHub HTTP API if possible. Exceptions during this process
    are logged and otherwise swallowed.

    Return Commit.id (DB primary key) of existing Commit entity or of newly
    created one. Expect database collision upon insert (in this case the ID for
    the existing commit entity is returned).

    Has slightly ~unpredictable run duration as of interaction with GitHub HTTP
    API.
    """

    def _guts(cinfo: TypeCommitInfoGitHub) -> Tuple[Commit, bool]:
        """
        Return a Commit object or raise `sqlalchemy.exc.IntegrityError`.

        The boolean return value means "created", is `False` if the first
        query for the commit object succeeds, else `True.
        """
        # Try to see if commit is already database. This is an optimization, to
        # not needlessly interact with the GitHub HTTP API in case the commit
        # is already in the database. first(): "Return the first result of this
        # Query or None if the result doesn’t contain any row.""
        dbcommit = Commit.first(sha=cinfo["commit_hash"], repository=cinfo["repo_url"])

        if dbcommit is not None:
            return dbcommit, False

        # Try to fetch metadata for commit via GitHub HTTP API. Fall back
        # gracefully if that does not work.
        gh_commit_metadata_dict = None
        try:
            # get_github_commit_metadata() may raise all those exceptions that can
            # happen during an HTTP request cycle. The repository might
            # for example not exist: Unexpected GitHub HTTP API response: <Response [404]
            gh_commit_metadata_dict = get_github_commit_metadata(cinfo)
        except Exception as exc:
            log.info(
                "treat as unknown context: error during get_github_commit_metadata(): %s",
                exc,
            )

        if gh_commit_metadata_dict:
            # We got data from GitHub. Insert into database.
            dbcommit = Commit.create_github_context(
                cinfo["commit_hash"], cinfo["repo_url"], gh_commit_metadata_dict
            )

            # The commit is known to GitHub. Fetch more data from GitHub.
            # Gracefully degrade if that does not work.
            try:
                backfill_default_branch_commits(cinfo["repo_url"], dbcommit)
            except Exception as exc:
                # Any error during this backfilling operation should not fail
                # the HTTP request processing (we're right now in the middle of
                # processing an HTTP request with new benchmark run data).
                log.info(
                    "Could not backfill default branch commits. Ignoring error "
                    "during backfill_default_branch_commits():  %s",
                    exc,
                )
                raise
            return dbcommit, True

        # Fetching metadata from GitHub failed. Store most important bits in
        # database.
        dbcommit = Commit.create_unknown_context(
            commit_hash=cinfo["commit_hash"], repo_url=cinfo["repo_url"]
        )
        return dbcommit, True

    created: bool = False
    t0 = time.monotonic()
    try:
        # `_guts()` is expected to raise IntegrityError when a concurrent racer
        # did insert the Commit object by now. This can happen, also see
        # https://github.com/conbench/conbench/issues/809
        commit, created = _guts(ghcommit)
    except s.exc.IntegrityError as exc:
        # Expected error example:
        #  sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation) \
        #    duplicate key value violates unique constraint "commit_index"
        log.info("Ignored IntegrityError while inserting Commit: %s", exc)
        # Look up the Commit entity again because this function must return the
        # commit ID (DB primary key).
        current_session.rollback()
        commit = Commit.first(
            sha=ghcommit["commit_hash"], repository=ghcommit["repo_url"]
        )

        # After IntegrityError we assume that Commit exists in DB. Encode
        # assumption, for easier debugging.
        assert commit is not None

    d_seconds = time.monotonic() - t0

    # Only log when the commit object was inserted (keep logs interesting,
    # reduce verbosity).
    if created:
        log.info(
            "commit_fetch_info_and_create_in_db_if_not_exists(%s) inserted, took %.3f s",
            ghcommit,
            d_seconds,
        )

    return commit


class _Serializer(EntitySerializer):
    def _dump(
        self, benchmark_result: "BenchmarkResult", get_baseline_runs: bool = False
    ):
        if benchmark_result.commit:
            commit_dict = CommitSerializer().one.dump(benchmark_result.commit)
            commit_dict.pop("links", None)
            commit_link = f.url_for(
                "api.commit", commit_id=commit_dict["id"], _external=True
            )
        else:
            commit_dict = None
            commit_link = None

        hardware_dict = HardwareSerializer().one.dump(benchmark_result.hardware)
        hardware_dict.pop("links", None)
        out_dict = {
            "id": benchmark_result.run_id,
            "tags": benchmark_result.run_tags,
            "reason": benchmark_result.run_reason,
            "name": benchmark_result.run_tags.get("name"),
            "timestamp": conbench.util.tznaive_dt_to_aware_iso8601_for_api(
                benchmark_result.run_tags["timestamp"]
            )
            if "timestamp" in benchmark_result.run_tags
            else None,
            "finished_timestamp": conbench.util.tznaive_dt_to_aware_iso8601_for_api(
                benchmark_result.run_tags["finished_timestamp"]
            )
            if "finished_timestamp" in benchmark_result.run_tags
            else None,
            "info": benchmark_result.run_tags.get("info"),
            "error_info": benchmark_result.run_tags.get("error_info"),
            "error_type": benchmark_result.run_tags.get("error_type"),
            "commit": commit_dict,
            "hardware": hardware_dict,
            "has_errors": benchmark_result.run_tags.get("has_errors"),
            "links": {
                "list": f.url_for("api.runs", _external=True),
                "self": f.url_for(
                    "api.run", run_id=benchmark_result.run_id, _external=True
                ),
                "hardware": f.url_for(
                    "api.hardware", hardware_id=hardware_dict["id"], _external=True
                ),
            },
        }
        if commit_link:
            out_dict["links"]["commit"] = commit_link
        if get_baseline_runs:
            out_dict["candidate_baseline_runs"] = get_candidate_baseline_runs(
                benchmark_result
            )
        return out_dict


class RunSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


class SchemaGitHubCreate(marshmallow.Schema):
    """
    GitHub-flavored commit info object
    """

    @marshmallow.pre_load
    def change_empty_string_to_none(self, data, **kwargs):
        """For the specific situation of empty string being provided,
        treat this a None, _before_ schema validation.

        This for example alles the client to set pr_number to an empty string
        and this has the same meaning as setting it to `null` in the JSON doc.

        Otherwise, an empty string results in 'Not a valid integer' (for
        pr_number, at least).
        """
        for k in ("pr_number", "branch"):
            if data.get(k) == "":
                data[k] = None

        return data

    commit = marshmallow.fields.String(
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                The commit hash of the benchmarked code.

                Must not be an empty string.

                Expected to be a known commit in the repository as specified
                by the `repository` URL property below.
                """
            )
        },
    )
    repository = marshmallow.fields.String(
        # Does this allow for empty strings or not?
        # Unclear, after reading marshmallow docs. Testes this. Yes, this
        # allows for empty string:
        # https://github.com/marshmallow-code/marshmallow/issues/76#issuecomment-1473348472
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                URL pointing to the benchmarked GitHub repository.

                Must be provided in the format https://github.com/org/repo.

                Trailing slashes are stripped off before database insertion.

                As of the time of writing, only URLs starting with
                "https://github.com" are allowed. Conbench interacts with the
                GitHub HTTP API in order to fetch information about the
                benchmarked repository. The Conbench user/operator is expected
                to ensure that Conbench is configured with a GitHub HTTP API
                authentication token that is privileged to read commit
                information for the repository specified here.

                Support for non-GitHub repositories (e.g. GitLab) or auxiliary
                repositories is interesting, but not yet well specified.
                """
            )
        },
    )
    pr_number = marshmallow.fields.Integer(
        required=False,
        allow_none=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                If set, this needs to be an integer or a stringified integer.

                This is the recommended way to indicate that this benchmark
                result has been obtained for a specific pull request branch.
                Conbench will use this pull request number to (try to) obtain
                branch information via the GitHub HTTP API.

                Set this to `null` or leave this out to indicate that this
                benchmark result has been obtained for the default branch.
                """
            )
        },
    )
    branch = marshmallow.fields.String(
        # All of these pass schema validation: empty string, non-empty-string,
        # null
        required=False,
        allow_none=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                This is an alternative way to indicate that this benchmark
                result has been obtained for a commit that is not on the
                default branch. Do not use this for GitHub pull requests (use
                the `pr_number` argument for that, see above).

                If set, this needs to be a string of the form `org:branch`.

                Warning: currently, if `branch` and `pr_number` are both
                provided, there is no error and `branch` takes precedence. Only
                use this when you know what you are doing.
                """
            )
        },
    )

    @marshmallow.validates_schema
    def validate_props(self, data, **kwargs):
        url = data["repository"]

        # Undocumented: transparently rewrite git@ to https:// URL -- let's
        # drop this in the future. Context:
        # https://github.com/conbench/conbench/pull/1134#discussion_r1170222541
        if url.startswith("git@github.com:"):
            url = url.replace("git@github.com:", "https://github.com/")
            data["repository"] = url

        if not url.startswith("https://github.com"):
            raise marshmallow.ValidationError(
                f"'repository' must be a URL, starting with 'https://github.com', got `{url}`"
            )

        try:
            urlparse(url)
        except ValueError as exc:
            raise marshmallow.ValidationError(
                f"'repository' failed URL validation: `{exc}`"
            )

        if not len(data["commit"]):
            raise marshmallow.ValidationError("'commit' must be a non-empty string")

    @marshmallow.post_load
    def turn_into_predictable_return_type(self, data, **kwargs) -> TypeCommitInfoGitHub:
        """
        We really have to look into schema-inferred tight types, this here is a
        quick workaround for the rest of the code base to be able to work with
        `TypeCommitInfoGitHub`.
        """

        url: str = data["repository"].rstrip("/")
        commit_hash: str = data["commit"]
        # If we do not re-add this here as `None` then this property is _not_
        # part of the output dictionary if the user left this key out of
        # their JSON object
        pr_number: Optional[int] = data.get("pr_number")
        branch: Optional[str] = data.get("branch")

        result: TypeCommitInfoGitHub = {
            "repo_url": url,
            "commit_hash": commit_hash,
            "pr_number": pr_number,
            "branch": branch,
        }

        return result


field_descriptions = {
    "finished_timestamp": (
        "A datetime string indicating the time at which the run finished. "
        "Expected to be in ISO 8601 notation. Timezone-aware notation "
        "recommended. Timezone-naive strings are interpreted in UTC. "
        "Fractions of seconds can be provided but are not returned by the "
        "API. Example value: 2022-11-25T22:02:42Z"
    ),
    "info": "Run's metadata",
    "error_info": "Metadata for run's error that prevented all or some benchmarks from running",
    "error_type": """Run's error type. Possible values: none, catastrophic, partial.
                    None = all attempted benchmarks are good.
                    Catastrophic =no benchmarks completed successfully.
                    Partial = some benchmarks completed, some failed""",
}


class _RunFacadeSchemaCreate(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    name = marshmallow.fields.String(required=False)
    reason = marshmallow.fields.String(required=False)
    finished_timestamp = marshmallow.fields.DateTime(
        required=False,
        metadata={"description": field_descriptions["finished_timestamp"]},
    )
    info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["info"]}
    )
    error_info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["error_info"]}
    )
    error_type = marshmallow.fields.String(
        required=False, metadata={"description": field_descriptions["error_type"]}
    )
    github = marshmallow.fields.Nested(
        SchemaGitHubCreate(),
        required=False,
        metadata={"description": github_commit_info_descr},
    )
    machine_info = marshmallow.fields.Nested(MachineSchema().create, required=False)
    cluster_info = marshmallow.fields.Nested(ClusterSchema().create, required=False)

    @marshmallow.post_load
    def recalc_finished_time(self, data, **kwargs):
        curdt = data.get("finished_timestamp")

        if curdt is None:
            return data

        data["finished_timestamp"] = conbench.util.dt_shift_to_utc(curdt)
        return data

    @marshmallow.validates_schema
    def validate_hardware_info_fields(self, data, **kwargs):
        if "machine_info" not in data and "cluster_info" not in data:
            raise marshmallow.ValidationError(
                "Either machine_info or cluster_info field is required"
            )
        if "machine_info" in data and "cluster_info" in data:
            raise marshmallow.ValidationError(
                "machine_info and cluster_info fields can not be used at the same time"
            )


class _RunFacadeSchemaUpdate(marshmallow.Schema):
    # `AwareDateTime` with `default_timezone` set to UTC: naive datetimes are
    # set this timezone.
    finished_timestamp = marshmallow.fields.AwareDateTime(
        required=False,
        format="iso",
        default_timezone=timezone.utc,
        metadata={
            "description": field_descriptions["finished_timestamp"],
        },
    )

    info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["info"]}
    )
    error_info = marshmallow.fields.Dict(
        required=False, metadata={"description": field_descriptions["error_info"]}
    )
    error_type = marshmallow.fields.String(
        required=False, metadata={"description": field_descriptions["error_type"]}
    )

    @marshmallow.post_load
    def recalc_finished_time(self, data, **kwargs):
        curdt = data.get("finished_timestamp")

        if curdt is None:
            return data

        data["finished_timestamp"] = conbench.util.dt_shift_to_utc(curdt)
        return data


class RunFacadeSchema:
    create = _RunFacadeSchemaCreate()
    update = _RunFacadeSchemaUpdate()
