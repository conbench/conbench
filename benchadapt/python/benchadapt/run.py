import uuid
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from . import _machine_info


@dataclass
class BenchmarkRun:
    """
    A dataclass for containing metadata on a run of benchmarks.

    Attributes
    ----------
    name : str
        Name for the run. Current convention is ``f"{reason}: {github['commit']}"``.
        If missing and ``github["commmit"]`` exists, ``name`` will be populated
        according to that pattern (even if ``reason`` is ``None``); otherwise it will
        remain ``None``. Users should not set this manually unless they want to identify
        runs in some other fashion. Benchmark name should be specified in ``tags["name"]``.
    id : str
        ID for the run. A hex UUID will be generated if not supplied.
    reason : str
        Reason for run (e.g. commit, PR, merge, nightly). Should be of low cardinality.
    info : Dict[str, Any]
        A schema-less dict of metadata about the run
    machine_info : Dict[str, Any]
        For benchmarks run on a single node, information about the machine, e.g. OS,
        architecture, etc. Auto-populated if ``cluster_info`` not set. If host name
        should not be detected with ``platform.node()`` (e.g. because a consistent
        name is needed for CI or cloud runners), it can be overridden with the
        ``CONBENCH_MACHINE_INFO_NAME`` environment variable.
    cluster_info : Dict[str, Any]
        For benchmarks run on a cluster, information about the cluster
    github : Dict[str, Any]
        Keys: ``repository`` (in the format ``org/repo``), ``commit``, and ``pr_number``.
        If this is a benchmark on the default branch, you may leave out ``pr_number``.
        If it's a non-default-branch & non-PR commit, you may supply the branch name to
        the optional ``branch`` key in the format ``org:branch``.

        By default, metadata will be obtained from ``CONBENCH_PROJECT_REPOSITORY``,
        ``CONBENCH_PROJECT_COMMIT``, and ``CONBENCH_PROJECT_PR_NUMBER`` environment variables.
        If any are unset, a warning will be raised.

        Advanced: if you have a locally cloned repo, you may explicitly supply ``None``
        to this argument and its information will be scraped from the cloned repo.
    finished_timestamp : str
        Timestamp the run finished, in ISO format, UTC or with timezone offset
    error_type: str
        Run's error type. Possible values: ``"none"``, ``"catastrophic"``, ``"partial"``.
        ``"none"``: all attempted benchmarks are good.
        ``"catastrophic"``: no benchmarks completed successfully.
        ``"partial"``: some benchmarks completed, some failed.
    error_info : Dict[str, Any]
        A dict containing information about errors raised when running the set of benchmark.
        Any schema is acceptable, but may contain stderr, a traceback, etc.

    Notes
    -----
    Fields one of which must be supplied, the other of which will not be posted to conbench:

    - ``machine_info`` (generated by default) or ``cluster_info``

    Fields without comprehensive defaults which should be specified directly:

    - ``reason``

    Fields with defaults you may want to override on instantiation:

    - ``name``
    - ``id``
    - ``info``
    - ``machine_info`` if not run on the current machine
    - ``cluster_info`` if run on a cluster
    - ``github``
    - ``finished_timestamp`` if run is now complete
    - ``error_type`` (if applicable)
    - ``error_info`` (if applicable)
    """

    name: str = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    reason: str = None
    info: Dict[str, Any] = field(default_factory=dict)
    machine_info: Dict[str, Any] = field(default_factory=_machine_info.machine_info)
    cluster_info: Dict[str, Any] = None
    github: Dict[str, Any] = field(default_factory=_machine_info.github_info)
    finished_timestamp: str = None
    error_type: str = None
    error_info: Dict[str, Any] = None

    def __post_init__(self) -> None:
        self._maybe_set_name()

    def _maybe_set_name(self) -> None:
        """
        Set a default value for `name` if not populated and `github["commit"]` is.
        Uses `reason`, but does not check if it's set, so may produce
        `None: <commit hash>`. Since reason and commit are required by the API, this
        should in most situations produce a reasonably useful `name`.
        """
        if not self.name and self.github.get("commit"):
            self.name = f"{self.reason}: {self.github['commit']}"

    @property
    def _github_property(self):
        return self._github_cache

    @_github_property.setter
    def _github_property(self, value: Optional[dict]):
        if value is None:
            value = _machine_info.detect_commit_info_from_local_git()
        self._github_cache = value
        self._maybe_set_name()

    @property
    def _cluster_info_property(self) -> Dict[str, Any]:
        return self._cluster_info_cache

    @_cluster_info_property.setter
    def _cluster_info_property(self, value: Dict[str, Any]) -> None:
        if value:
            self.machine_info = None
        self._cluster_info_cache = value

    def to_publishable_dict(self):
        """Returns a dict suitable for sending to conbench"""
        res_dict = asdict(self)

        if bool(res_dict.get("machine_info")) != bool(not res_dict["cluster_info"]):
            warnings.warn(
                "Run not publishable! `machine_info` xor `cluster_info` must be specified"
            )

        if not (
            res_dict["github"].get("repository") and res_dict["github"].get("commit")
        ):
            raise ValueError(
                "Run not publishable! `github.repository` and `github.commit` must be populated. "
                "You may pass github metadata via CONBENCH_PROJECT_REPOSITORY, CONBENCH_PROJECT_COMMIT, "
                "and CONBENCH_PR_NUMBER environment variables. "
                f"\ngithub: {res_dict['github']}"
            )

        for attr in [
            "name",
            "machine_info",
            "cluster_info",
            "finished_timestamp",
            "error_type",
            "error_info",
        ]:
            if not res_dict[attr]:
                res_dict.pop(attr)

        return res_dict


# Ugly, but per https://stackoverflow.com/a/61480946 lets us keep defaults and order
BenchmarkRun.cluster_info = BenchmarkRun._cluster_info_property
BenchmarkRun.github = BenchmarkRun._github_property
