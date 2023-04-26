import datetime
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Union, Literal

from . import _machine_info


@dataclass
class BenchmarkResult:
    """
    A dataclass for containing results from running a benchmark.

    Attributes
    ----------
    run_name : str
        Name for the run. Current convention is ``f"{run_reason}: {github['commit']}"``.
        If missing and ``github["commmit"]`` exists, ``run_name`` will be populated
        according to that pattern (even if ``run_reason`` is ``None``); otherwise it will
        remain ``None``. Users should not set this manually unless they want to identify
        runs in some other fashion. Benchmark name should be specified in ``tags["name"]``.
    run_id : str
        ID for the run; should be consistent for all results of the run. Should not normally
        be set manually; adapters will handle this for you.
    batch_id : str
        ID string for the batch
    run_reason : str
        Reason for run (e.g. commit, PR, merge, nightly). In many cases will be set at
        runtime via an adapter's ``result_fields_override`` init parameter; should not
        usually be set in ``_transform_results()``.
    timestamp : str
        Timestamp of call, in ISO format
    stats : Dict[str, Any]
        Measurement data and summary statistics. If ``data`` (a list of metric values),
        ``unit`` (for that metric, e.g. ``"s"``), and ``iterations`` (replications for
        microbenchmarks) are specified, summary statistics will be filled in server-side.
    error : Dict[str, Any]
        A dict containing information about errors raised when running the benchmark. Any
        schema is acceptable, but may contain stderr, a traceback, etc.
    validation : Dict [str, Any]
        Benchmark results validation metadata (e.g., errors, validation types).
    tags : Dict[str, Any]
        Many things. Must include a ``name`` element (i.e. the name corresponding to the
        benchmark code); often includes parameters either as separate keys or as a string
        in a ``params`` key. If suite subdivisions exist, use a ``suite`` tag. Determines
        history runs.
    info : Dict[str, Any]
        Things like ``arrow_version``, ``arrow_compiler_id``, ``arrow_compiler_version``,
        ``benchmark_language_version, ``arrow_version_r``
    optional_benchmark_info : Dict[str, Any]
        Optional information about Benchmark results (e.g., telemetry links, logs links).
        These are unique to each benchmark that is run, but are information that aren't
        reasonably expected to impact benchmark performance. Helpful for adding debugging
        or additional links and context for a benchmark (free-form JSON)
    machine_info : Dict[str, Any]
        For benchmarks run on a single node, information about the machine, e.g. OS,
        architecture, etc. Auto-populated if ``cluster_info`` not set. If host name
        should not be detected with ``platform.node()`` (e.g. because a consistent
        name is needed for CI or cloud runners), it can be overridden with the
        ``CONBENCH_MACHINE_INFO_NAME`` environment variable.
    cluster_info : Dict[str, Any]
        For benchmarks run on a cluster, information about the cluster
    context : Dict[str, Any]
        Should include ``benchmark_language`` and other relevant metadata like compiler flags
    github : Union[Optional[Dict[str, Any]], Literal["inspect_git_in_cwd"]

        A dictionary containing GitHub-flavored commit information.

        Allowed values: `None`, no value, a dictionary.

        Not passing an argument upon dataclass construction results in inspection
        of the environment variables ``CONBENCH_PROJECT_REPOSITORY``,
        ``CONBENCH_PROJECT_COMMIT``, and ``CONBENCH_PROJECT_PR_NUMBER``.
        If any of those are not set, a warning is raised.

        Passing `None` explicitly defines that this result is not associated
        with any commit.

        Not associating a benchmark result with commit information has special,
        limited purpose (pre-merge benchmarks, testing). It generally means
        that this benchmark result will not be considered for time series
        analysis along a commit tree.

        If passed a dictionary, it should have the following keys:
        - required: ``repository`` (string, in the format ``https://github.com/<org>/<repo>``)
        - required: ``commit`` (string, the full commit hash)
        - recommended: ``pr_number`` (stringified integer) or ``branch`` (string)

        If the benchmark was run gainst the default branch, you may leave
        out ``pr_number`` and ``branch``.

        If it was run on a GitHub pull request branch, you should provide the
        ``pr_number``.

        If it was run on a non-default branch and a non-PR commit, you may
        supply the branch name via the ``branch`` set to a value of the format
        ``org:branch``.

        Deprecated: pass the special value "inspect_git_in_cwd" to try to
        attempt commit hash / remote URL / branch information from a .git
        directory in the current working directory via executing git commands
        as child processes. This raises an exception when any of the commands
        fails.

    Notes
    -----
    Fields one of which must be supplied:

    - ``machine_info`` (generated by default) xor ``cluster_info``
    - ``stats`` or ``error``

    Fields which should generally not be specified directly on instantiation that will
    be set later for the run:

    - ``run_name``
    - ``run_id``
    - ``run_reason``

    Fields without comprehensive defaults which should be specified directly:

    - ``stats`` (and/or ``error``)
    - ``validation``
    - ``tags``
    - ``info``
    - ``optional_benchmark_info``
    - ``context``

    Fields with defaults you may want to override on instantiation:

    - ``batch_id`` if multiple benchmarks should be grouped, e.g. for a suite
    - ``timestamp`` if run time is inaccurate
    - ``machine_info`` if not run on the current machine
    - ``cluster_info`` if run on a cluster
    - ``github``

    If a result with a new ``run_id`` is posted, a new record for the run will be
    created. If a run record with that ID already exists, either because of a
    previous result or the run being posted directly, the following fields will be
    effectively ignored, as they are only stored on the run:

    - ``run_name``
    - ``run_reason``
    - ``github``
    - ``machine_info``
    - ``cluster_info``
    """

    run_name: str = None
    run_id: str = None
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    run_reason: str = None
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    stats: Dict[str, Any] = None
    error: Dict[str, Any] = None
    validation: Dict[str, Any] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    info: Dict[str, Any] = field(default_factory=dict)
    optional_benchmark_info: Dict[str, Any] = None
    machine_info: Dict[str, Any] = field(default_factory=_machine_info.machine_info)
    cluster_info: Dict[str, Any] = None
    context: Dict[str, Any] = field(default_factory=dict)
    github: Union[Optional[Dict[str, str]], Literal["inspect_git_in_cwd"]] = field(
        default_factory=_machine_info.gh_commit_info_from_env
    )

    def __post_init__(self) -> None:
        self._maybe_set_run_name()

    def _maybe_set_run_name(self) -> None:
        """
        Set a default value for `run_name` if not populated and `github["commit"]` is.
        Uses `run_reason`, but does not check if it's set, so may produce
        `None: <commit hash>`. Since `run_reason` and commit are required by the API,
        this should in most situations produce a reasonably useful `run_name`.
        """
        if not self.run_name:
            if isinstance(self.github, dict):
                if self.github.get("commit"):
                    self.run_name = f"{self.run_reason}: {self.github['commit']}"

    @property
    def _github_property(self):
        return self._github_cache

    @_github_property.setter
    def _github_property(
        self, value: Union[Optional[Dict[str, str]], Literal["inspect_git_in_cwd"]]
    ):
        if value == "inspect_git_in_cwd":
            value = _machine_info.detect_commit_info_from_local_git_or_raise()
        else:
            # Better: schema validation
            if not value is None and not isinstance(value, dict):
                raise Exception(f"unexpected value for `github` property: {value}")

        self._github_cache = value
        self._maybe_set_run_name()

    @property
    def _cluster_info_property(self) -> Dict[str, Any]:
        return self._cluster_info_cache

    @_cluster_info_property.setter
    def _cluster_info_property(self, value: Dict[str, Any]) -> None:
        if value:
            self.machine_info = None
        self._cluster_info_cache = value

    def to_publishable_dict(self) -> Dict:
        """
        Return a dictionary representing the benchmark result.

        After JSON-serialization, that dictionary is expected to validate
        against the JSON schema that the Conbench API expects on the endpoint
        for benchmark result submission.
        """

        res_dict = asdict(self)

        # We should discuss why we don't exit with an error here (publish this
        # although it's not publishable? who consumes the warning? should the
        # warning be re-worded to be more user-friendly?)
        if bool(res_dict.get("machine_info")) != bool(not res_dict["cluster_info"]):
            warnings.warn(
                "Result not publishable! `machine_info` xor `cluster_info` must be specified"
            )

        if not res_dict["stats"] and not res_dict["error"]:
            warnings.warn(
                "Result not publishable! `stats` and/or `error` must be be specified"
            )

        validate_or_remove_github_commit_key(res_dict)

        for attr in [
            "run_name",
            "optional_benchmark_info",
            "machine_info",
            "cluster_info",
            "stats",
            "error",
            "validation",
        ]:
            if not res_dict[attr]:
                res_dict.pop(attr)

        return res_dict


def validate_or_remove_github_commit_key(res_dict: Dict, strict=False):
    """
    Mutate BenchmarkResult dictionary in-place to make its `github` key
    property be compliant with the Conbench HTTP API.

    Not providing the `github` key in result dictionary tells Conbench that
    this result is commit-context-less (recording it in Conbench might be
    useful for debugging and testing purposes, but generally we should make
    clear that this implies missing out on critical features/purpose).
    """

    def _warn_or_raise():
        msg = (
            "This dictionary does not contain commit information. "
            "This might be intended (for a so-called pre-merge benchmark "
            "result). If it is not intended then you might be accidentally "
            "missing out on those Conbench capabilities that associate "
            "benchmark results with code changes. For automatically "
            "adding commit information, set the CONBENCH_PROJECT_* family "
            "of environment variables before dataclass instantiation (see API "
            "docs for details)."
        )
        if strict:
            raise ValueError(msg)

        warnings.warn(msg)

    if res_dict["github"] is None:
        # Tis means: "no commit information present", and this was desired by
        # the user (i.e., be quiet and do as demanded by user). Normalize this
        # state into the the one way to tell the Conbench HTTP API "no commit
        # info": remove the key from the BenchmarkResult dict.
        del res_dict["github"]
        return

    for checkkey in ("repository", "commit"):
        if checkkey not in res_dict["github"]:
            _warn_or_raise()
            # Normalize this state into the recommended, single way to say "no
            # commit info": remove the key from the BenchmarkResult dict..
            del res_dict["github"]
            break


# Ugly, but per https://stackoverflow.com/a/61480946 lets us keep defaults and order
BenchmarkResult.cluster_info = BenchmarkResult._cluster_info_property
BenchmarkResult.github = BenchmarkResult._github_property
