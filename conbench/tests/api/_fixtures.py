import copy
from datetime import datetime
from typing import Dict, List, Tuple

from ...entities.benchmark_result import BenchmarkResult
from ...entities.commit import Commit
from ...runner import Conbench
from ...tests.helpers import _uuid

CHILD = "02addad336ba19a654f9c857ede546331be7b631"
PARENT = "4beb514d071c9beec69b8917b5265e77ade22fb3"
GRANDPARENT = "6d703c4c7b15be630af48d5e9ef61628751674b2"
ELDER = "81e9417eb68171e03a304097ae86e1fd83307130"

REPO = "https://github.com/org/something"

RESULTS_UP = [[1, 2, 3], [2, 3, 4], [10, 20, 30]]
RESULTS_DOWN = [[10, 11, 12], [11, 12, 13], [1, 2, 3]]
Z_SCORE_UP = 24.74873734152916  # Computed using statistics.stdev()
Z_SCORE_DOWN = -13.435028842544401  # Computed using statistics.stdev()

CLUSTER_INFO = {
    "name": f"cluster-{_uuid()}",
    "info": {"gpu": 1},
    "optional_info": {"workers": 1},
}

MACHINE_INFO = {
    "architecture_name": "x86_64",
    "cpu_l1d_cache_bytes": "32768",
    "cpu_l1i_cache_bytes": "32768",
    "cpu_l2_cache_bytes": "262144",
    "cpu_l3_cache_bytes": "4194304",
    "cpu_core_count": "2",
    "cpu_frequency_max_hz": "3500000000",
    "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
    "cpu_thread_count": "4",
    "kernel_name": "19.6.0",
    "memory_bytes": "17179869184",
    "name": "diana",
    "os_name": "macOS",
    "os_version": "10.15.7",
    "gpu_count": "2",
    "gpu_product_names": ["Tesla T4", "GeForce GTX 1060 3GB"],
}

VALID_PAYLOAD = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "run_reason": "commit",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:44Z",
    "context": {
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "benchmark_language": "Python",
    },
    "info": {
        "arrow_version": "2.0.0",
        "benchmark_language_version": "Python 3.8.5",
        "arrow_compiler_version": "11.0.0.11000033",
        "arrow_compiler_id": "AppleClang",
    },
    "optional_benchmark_info": {"trace_id": "some trace id", "logs": "some log uri"},
    "validation": {"type": "pandas.testing", "success": True},
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/org/repo",
        "branch": None,
        "pr_number": 12345678,
    },
    "machine_info": MACHINE_INFO,
    "stats": {
        "data": [
            "0.099094",
            "0.037129",
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "times": [
            "0.099094",
            "0.037129",
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "unit": "s",
        "time_unit": "s",
        "iqr": "0.030442",
        "iterations": 10,
        "max": "0.148896",
        "mean": "0.036369",
        "median": "0.008988",
        "min": "0.004733",
        "q1": "0.006500",
        "q3": "0.036942",
        "stdev": "0.049194",
    },
    "tags": {
        "compression": "snappy",
        "cpu_count": "2",
        "dataset": "nyctaxi_sample",
        "file_type": "parquet",
        "input_type": "arrow",
        "name": "file-write",
    },
}

VALID_PAYLOAD_WITH_ERROR = dict(
    run_id="ya5709d179f349cba69ed242be3e6323",
    error={"stack_trace": "some trace", "command": "ls"},
    **{
        key: value
        for key, value in VALID_PAYLOAD.items()
        if key not in ("stats", "run_id")
    },
)

VALID_PAYLOAD_WITH_ITERATION_ERROR = dict(
    run_id="ya5709d179f349cba69ed242be3e6323",
    error={"stack_trace": "some trace", "command": "ls"},
    **{
        key: value
        for key, value in VALID_PAYLOAD.items()
        if key not in ("stats", "run_id")
    },
    stats={
        "data": [
            "0.099094",
            None,
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "times": [
            "0.099094",
            None,
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "unit": "s",
        "time_unit": "s",
        "iterations": 10,
    },
)

VALID_PAYLOAD_FOR_CLUSTER = dict(
    run_id="3a5709d179f349cba69ed242be3e6323",
    cluster_info=CLUSTER_INFO,
    **{
        key: value
        for key, value in VALID_PAYLOAD.items()
        if key not in ("machine_info", "run_id")
    },
)

VALID_RUN_PAYLOAD = {
    "id": _uuid(),
    "name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "reason": "commit",
    "finished_timestamp": "2020-11-25T21:02:42Z",
    "info": {
        "setup": "passed",
    },
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/org/repo",
        "branch": None,
        "pr_number": 12345678,
    },
    "machine_info": MACHINE_INFO,
}

VALID_RUN_PAYLOAD_FOR_CLUSTER = dict(
    id=_uuid(),
    cluster_info=CLUSTER_INFO,
    **{
        key: value
        for key, value in VALID_RUN_PAYLOAD.items()
        if key not in ("machine_info", "id")
    },
)

VALID_RUN_PAYLOAD_WITH_ERROR = dict(
    id=_uuid(),
    error_info={"error": "error", "stack_trace": "stack_trace", "fatal": True},
    error_type="fatal",
    **{key: value for key, value in VALID_RUN_PAYLOAD.items() if key not in ("id")},
)


def benchmark_result(
    name=None,
    batch_id=None,
    run_id=None,
    results=None,
    unit=None,
    language=None,
    hardware_type="machine",
    hardware_name=None,
    sha=None,
    commit=None,
    pull_request=False,
    error=None,
    empty_results=False,
    reason=None,
):
    """Create BenchmarkResult and write to database."""

    data = copy.deepcopy(VALID_PAYLOAD)
    data["run_name"] = f"commit: {_uuid()}"
    data["run_reason"] = reason if reason else "commit"
    data["run_id"] = run_id if run_id else _uuid()
    data["batch_id"] = batch_id if batch_id else _uuid()
    data["tags"]["name"] = name if name else _uuid()

    if language:
        data["context"]["benchmark_language"] = language
    if hardware_name:
        data[f"{hardware_type}_info"]["name"] = hardware_name
    if pull_request:
        data["run_name"] = "pull request: some commit"
        data["run_reason"] = "pull request"
    if sha:
        data["github"]["commit"] = sha
    if commit:
        data["github"]["commit"] = commit.sha
        data["github"]["repository"] = commit.repository
        data["github"]["branch"] = commit.branch

    if results is not None:
        unit = unit if unit else "s"
        data["stats"] = Conbench._stats(results, unit, [], "s")

    if empty_results:
        data.pop("stats", None)

    if error is not None:
        data["error"] = error

    return BenchmarkResult.create(data)


def gen_fake_data() -> Tuple[Dict[str, Commit], List[BenchmarkResult]]:
    """Populate the database with fake Commits and BenchmarkResults to use when testing
    most of the entities.

    Return a dict of commits (keyed by SHA) and list of BenchmarkResults.
    """
    # Manually post all the Commits to the database first, so that upon posting
    # BenchmarkResults, the server doesn't hit the GitHub API for more commit information.
    commits: Dict[str, Commit] = {}

    # Populate default branch commits. No holes because they should always be backfilled.
    for sha, timestamp, parent in [
        ("11111", datetime(2022, 1, 1), None),
        ("22222", datetime(2022, 1, 2), "11111"),
        ("33333", datetime(2022, 1, 3), "22222"),
        ("44444", datetime(2022, 1, 4), "33333"),
        ("55555", datetime(2022, 1, 5), "44444"),
        ("66666", datetime(2022, 1, 6), "55555"),
    ]:
        commits[sha] = Commit.create(
            {
                "sha": sha,
                "branch": "default",
                "fork_point_sha": sha,
                "parent": parent,
                "repository": REPO,
                "message": "message",
                "author_name": "author_name",
                "timestamp": timestamp,
            }
        )

    # Populate dev branch commits. Start forked off 22222 and rebase a few times.
    # (Note: when someone rebases, a new commit is created with a different SHA and
    # parent graph, but the same timestamp.)
    for sha, timestamp, parent, fork_point_sha in [
        # start at 22222
        ("aaaaa", datetime(2022, 1, 2, 10), "22222", "22222"),
        ("bbbbb", datetime(2022, 1, 3, 10), "aaaaa", "22222"),
        # rebase to 33333
        ("ccccc", datetime(2022, 1, 2, 10), "33333", "33333"),
        ("ddddd", datetime(2022, 1, 3, 10), "ccccc", "33333"),
        # rebase to 44444
        ("eeeee", datetime(2022, 1, 2, 10), "44444", "44444"),
        ("fffff", datetime(2022, 1, 3, 10), "eeeee", "44444"),
        # new commit on the branch
        ("00000", datetime(2022, 1, 4, 10), "fffff", "44444"),
    ]:
        commits[sha] = Commit.create(
            {
                "sha": sha,
                "branch": "branch",
                "fork_point_sha": fork_point_sha,
                "parent": parent,
                "repository": REPO,
                "message": "message",
                "author_name": "author_name",
                "timestamp": timestamp,
            }
        )

    # now a commit to a different repo
    commits["abcde"] = Commit.create(
        {
            "sha": "abcde",
            "branch": "default",
            "fork_point_sha": "abcde",
            "parent": "12345",
            "repository": "https://github.com/org/something_else",
            "message": "message",
            "author_name": "author_name",
            "timestamp": datetime(2022, 1, 3),
        }
    )

    # commits with less context
    commits["sha"] = Commit.create_unknown_context(
        hash="sha", repo_url="https://github.com/org/something_else_entirely"
    )
    commits[""] = Commit.create_no_context()

    # Now populate a variety of different BenchmarkResults
    benchmark_results: List[BenchmarkResult] = []
    name = _uuid()

    for data_or_error, commit_sha in [
        # first commit
        ([2.1, 2.0, 1.9], "11111"),
        # stayed the sameish
        ([2.2, 2.0, 2.1], "22222"),
        # failed on PR
        ({"stack_trace": "..."}, "aaaaa"),
        # fixed the PR
        ([2.0, 2.1, 1.9], "bbbbb"),
        # 33333 failed in CI and never reported any results :(
        # rebased the PR onto 33333 (ccccc wasn't measured)
        ([1.9, 2.0, 1.8], "ddddd"),
        # a different change made the default branch better
        ([1.2, 1.1, 1.0], "44444"),
        # rebased the PR (eeeee wasn't measured)
        ([1.0, 1.2, 1.1], "fffff"),
        # PR got worse
        ([3.1, 3.0, 2.9], "00000"),
        # 55555 failed in CI and never reported any results :(
        # 66666 got even worse
        ([4.1, 4.0, 4.9], "66666"),
        # another run on 66666 (note: one more with different reason below)
        ([4.5, 4.6, 4.7], "66666"),
        # on a different repo
        ({"error": "bad"}, "abcde"),
        # some-context commit
        ([20.0, 20.1, 20.2], "sha"),
        # no-context commit
        ([10.0, 10.1, 10.2], ""),
    ]:
        commit = commits[commit_sha]
        if isinstance(data_or_error, list):
            benchmark_results.append(
                benchmark_result(
                    results=data_or_error,
                    commit=commit,
                    name=name,
                    pull_request=commit.branch == "branch",
                )
            )
        else:
            benchmark_results.append(
                benchmark_result(
                    error=data_or_error,
                    commit=commit,
                    name=name,
                    pull_request=commit.branch == "branch",
                )
            )

    # A few more on commit 66666
    for kwargs in [
        # different case
        {"name": "different-case"},
        # different context
        {"language": "different-language"},
        # different machine
        {"hardware_name": "different-hardware"},
        # different reason (still is comparable)
        {"reason": "nightly"},
    ]:
        this_name = kwargs.pop("name", name)
        benchmark_results.append(
            benchmark_result(
                results=[5.1, 5.2, 5.3],
                commit=commits["66666"],
                name=this_name,
                **kwargs,
            )
        )

    return commits, benchmark_results
