import datetime
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from .machine_info import github_info, machine_info


@dataclass
class BenchmarkResult:
    """
    A dataclass for containing results from running a benchmark.

    Attributes
    ----------
    run_name : str
        run name
    run_id : str
        ID string for the run
    batch_id : str
        ID string for the batch
    run_reason : str
        Reason for run (e.g. "nightly")
    timestamp : str
        Timestamp of call, in ISO format
    stats : Dict[str, Any]
        Measurement data and summary statistics
    tags : Dict[str, Any]
        Many things. Determines history runs
    info : Dict[str, Any]
        Things like ``arrow_version``, ``arrow_compiler_id``, ``arrow_compiler_version``,
        ``benchmark_language_version, ``arrow_version_r``
    machine_info : Dict[str, Any]
        For benchmarks run on a single node, information about the machine, e.g. OS,
        architecture, etc.
    cluster_info : Dict[str, Any]
        For benchmarks run on a cluster, information about the cluster
    context : Dict[str, Any]
        ``arrow_compiler_flags``, ``benchmark_language``
    github : Dict[str, Any]
        ``repository``, ``commit``
    error : str
        stderr from process running the benchmark

    Fields one of which must be supplied, the other of which will not be posted to conbench:

    - ``machine_info`` or ``cluster_info``
    - ``stats`` or ``error``
    """

    run_name: str = None
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    run_reason: str = None
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    stats: Dict[str, Any] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    info: Dict[str, Any] = None
    machine_info: Dict[str, Any] = None
    cluster_info: Dict[str, Any] = None
    context: Dict[str, Any] = None
    github: Dict[str, Any] = field(default_factory=github_info)
    error: str = None

    def __post_init__(self):
        if not self.machine_info and not self.cluster_info:
            self.machine_info = machine_info(host_name=None)

    def to_publishable_dict(self):
        """Returns a dict suitable for sending to conbench"""
        res_dict = asdict(self)

        if bool(res_dict.get("machine_info")) != bool(not res_dict["cluster_info"]):
            warnings.warn(
                "Result not publishable! `machine_info` xor `cluster_info` must be specified"
            )

        if bool(res_dict["stats"]) == bool(res_dict["error"]):
            warnings.warn(
                "Result not publishable! `stats` xor `error` must be be specified"
            )

        for attr in ["machine_info", "cluster_info", "stats", "error"]:
            if not res_dict[attr]:
                res_dict.pop(attr)

        return res_dict
