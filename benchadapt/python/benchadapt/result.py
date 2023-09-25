import datetime
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from . import _machine_info


@dataclass
class BenchmarkResult:
    """
    A dataclass for containing results from running a benchmark.

    Attributes
    ----------
    run_name : str
        Name for the run. Current convention is ``f"{run_reason}: {github['commit']}"``.
        If missing and ``github["commit"]`` exists, ``run_name`` will be populated
        according to that pattern (even if ``run_reason`` is ``None``); otherwise it will
        remain ``None``. Users should not set this manually unless they want to identify
        runs in some other fashion. Benchmark name should be specified in ``tags["name"]``.

        This argument is deprecated and will be removed in the future. Any given name
        here will be added to ``run_tags`` under the "name" key on the server side.
    run_id : str
        ID for the run; should be consistent for all results of the run. Should not normally
        be set manually; adapters will handle this for you.
    run_tags : Dict[str, str]
        An optional mapping of arbitrary keys and values that describe the CI run. These
        are used to group and filter runs in the UI and API. Do not include
        ``run_reason`` here; it should be provided below.

        The Conbench UI and API assume that all benchmark results with the same
        ``run_id`` share the same ``run_tags``. There is no technical enforcement of
        this on the server side, so some behavior may not work as intended if this
        assumption is broken by the client.
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
    github : Dict[str, Any]
        A dictionary containing GitHub-flavored commit information.

        Allowed values: no value, a special dictionary.

        Not passing an argument upon dataclass construction results in inspection
        of the environment variables ``CONBENCH_PROJECT_REPOSITORY``,
        ``CONBENCH_PROJECT_COMMIT``, and ``CONBENCH_PROJECT_PR_NUMBER``, which are
        used as the special dictionary's ``repository``, ``commit``, and ``pr_number``
        keys respectively, if they are set. These are defined below.

        If passed a dictionary, it must have at least the ``repository`` key, which must
        be a string, in the format ``https://github.com/<org>/<repo>``.

        If the benchmark was run on a reproducible commit (from the default branch or a
        pull request commit), it must also have the ``commit`` key, which must be a
        string of the full commit hash. Not associating a benchmark result with a commit
        hash has special, limited purpose (pre-merge benchmarks, testing). It generally
        means that this benchmark result will not be considered for time series analysis
        along a commit tree.

        If the benchmark was run against the default branch, do not specify
        additional keys.

        If it was run on a GitHub pull request branch, you should provide
        ``pr_number``.

        If it was run on a non-default branch and a non-PR commit, you may
        supply the branch name via the ``branch`` set to a value of the format
        ``org:branch``.

        For more details, consult the Conbench HTTP API specification.

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
    - ``run_tags``

    Fields with defaults you may want to override on instantiation:

    - ``batch_id`` if multiple benchmarks should be grouped, e.g. for a suite
    - ``timestamp`` if run time is inaccurate
    - ``machine_info`` if not run on the current machine
    - ``cluster_info`` if run on a cluster
    - ``github``
    """

    run_name: str = None
    run_id: str = None
    run_tags: Dict[str, str] = field(default_factory=dict)
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
    github: Dict[str, str] = field(
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
            if self.github.get("commit"):
                self.run_name = f"{self.run_reason}: {self.github['commit']}"

    @property
    def _github_property(self):
        return self._github_cache

    @_github_property.setter
    def _github_property(self, value: Dict[str, str]):
        # Better: schema validation
        if not isinstance(value, dict):
            raise TypeError(f"unexpected type for `github` property: {value}")

        if "repository" not in value:
            raise ValueError(f"missing `repository` key in `github` property: {value}")

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


# Ugly, but per https://stackoverflow.com/a/61480946 lets us keep defaults and order
BenchmarkResult.cluster_info = BenchmarkResult._cluster_info_property
BenchmarkResult.github = BenchmarkResult._github_property
