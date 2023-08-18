import os
import platform
import re
import subprocess
import warnings


def _sysctl(stat):
    return ["sysctl", "-n", stat]


MUST_BE_INTS = [
    "cpu_core_count",
    "cpu_thread_count",
    "cpu_frequency_max_hz",
    "cpu_l1d_cache_bytes",
    "cpu_l1i_cache_bytes",
    "cpu_l2_cache_bytes",
    "cpu_l3_cache_bytes",
    "memory_bytes",
    "gpu_count",
]


COMMANDS = {
    "kernel_name": ["uname", "-r"],
    "cpu_model_name": _sysctl("machdep.cpu.brand_string"),
    "cpu_core_count": _sysctl("hw.physicalcpu"),
    "cpu_thread_count": _sysctl("hw.logicalcpu"),
    "cpu_frequency_max_hz": _sysctl("hw.cpufrequency_max"),
    "cpu_l1d_cache_bytes": _sysctl("hw.l1dcachesize"),
    "cpu_l1i_cache_bytes": _sysctl("hw.l1icachesize"),
    "cpu_l2_cache_bytes": _sysctl("hw.l2cachesize"),
    "cpu_l3_cache_bytes": _sysctl("hw.l3cachesize"),
    "memory_bytes": _sysctl("hw.memsize"),
}


LSCPU_MAPPING = {
    "cpu_model_name": "Model name",
    "cpu_frequency_max_hz": "CPU max MHz",
    "cpu_l1d_cache_bytes": "L1d cache",
    "cpu_l1i_cache_bytes": "L1i cache",
    "cpu_l2_cache_bytes": "L2 cache",
    "cpu_l3_cache_bytes": "L3 cache",
}

MEMINFO_MAPPING = {
    "memory_bytes": "MemTotal",
}

NVIDIA_SMI_MAPPING = {
    "gpu_count": None,
    "gpu_product_names": None,
}

CPUINFO_MAPPING = {
    "cpu_model_name": "brand_raw",
    "cpu_l1d_cache_bytes": "l1_data_cache_size",
    "cpu_l1i_cache_bytes": "l1_instruction_cache_size",
    "cpu_l2_cache_bytes": "l2_cache_size",
    "cpu_l3_cache_bytes": "l3_cache_size",
}


def python_info():
    version = _exec_command(["python", "--version"])
    return {
        "benchmark_language": "Python",
        "benchmark_language_version": version,
    }


def r_info():
    r = "cat(version[['version.string']], '\n')"
    version = _exec_command(["R", "-s", "-q", "-e", r])
    return {
        "benchmark_language": "R",
        "benchmark_language_version": version,
    }


class GitParseWarning(RuntimeWarning):
    pass


def github_info():
    """Attempts to inspect a locally cloned repository for git information that can be
    posted to the "github" key when creating a run.

    It's recommended to NOT use this function, and instead manually supply the commit
    and repository (in the form "org/repo"). When doing so, ignore the "branch" key
    and only supply the "pr_number" (or leave it None if it's a commit to the default
    branch).
    """
    commit = _exec_command(["git", "rev-parse", "HEAD"])
    if not commit:
        warnings.warn(
            "error in github_info(): probably not in a git repo; returning {}",
            GitParseWarning,
        )
        return {}

    branches = _exec_command(["git", "branch", "-vv"])
    if "* (HEAD detached" in branches:
        remote = "origin"
        branch = "<DETATCHED BRANCH>"
        warnings.warn(
            f"error in github_info(): detached HEAD; returning {branch=}",
            GitParseWarning,
        )

    else:
        current_branch = [b for b in branches.split("\n") if b.startswith("*")][0]
        _, branch_name, _, upstream, *_ = current_branch.split()
        if not upstream.startswith("["):
            remote = "origin"
            branch = _exec_command(["git", "branch", "--show-current"])
            warnings.warn(
                f"error in github_info(): untracked branch; returning {branch=}",
                GitParseWarning,
            )
        else:
            remote = upstream[1:].split("/")[0]
            branch = branch_name

    remote_url = _exec_command(["git", "remote", "get-url", remote])
    fork = re.search("(?<=.com[/:])([^/]*?)(?=/)", remote_url).group(0)

    return {
        "commit": commit,
        "repository": remote_url.rsplit(".git")[0],
        "branch": f"{fork}:{branch}",
        "pr_number": None,
    }


def machine_info(host_name):
    os_name, os_version = platform.platform(terse=True).split("-", maxsplit=1)

    host_name = host_name or os.environ.get("CONBENCH_MACHINE_INFO_NAME")
    host_name = host_name or platform.node()

    info = {
        "name": host_name,
        "os_name": os_name,
        "os_version": os_version,
        "architecture_name": platform.machine(),
        "kernel_name": None,
        "memory_bytes": None,
        "cpu_model_name": None,
        "cpu_core_count": None,
        "cpu_thread_count": None,
        "cpu_l1d_cache_bytes": None,
        "cpu_l1i_cache_bytes": None,
        "cpu_l2_cache_bytes": None,
        "cpu_l3_cache_bytes": None,
        "cpu_frequency_max_hz": None,
        "gpu_count": None,
        "gpu_product_names": [],
    }

    _commands(info)
    _meminfo(info)
    _lscpu(info)
    _cpuinfo(info)
    _psutil(info)
    _nvidia_smi(info)

    for key in MUST_BE_INTS:
        try:
            int(info[key])
        except (ValueError, TypeError):
            info[key] = 0

    info["memory_bytes"] = _round_memory(int(info["memory_bytes"]))

    for key in info:
        if not isinstance(info[key], list):
            info[key] = str(info[key])

    return info


def _round_memory(value):
    # B -> GiB -> B
    gigs = 1024**3
    return int("{:.0f}".format(value / gigs)) * gigs


def _commands(info):
    for key, command in COMMANDS.items():
        try:
            result = _exec_command(command)
            info[key] = result if result else ""
        except:
            info[key] = ""


def _psutil(info):
    # TODO: rename to cpu_count_logical
    if not info["cpu_thread_count"]:
        info["cpu_thread_count"] = os.cpu_count()

    try:
        import psutil

        # TODO: rename to cpu_count_physical
        if not info["cpu_core_count"]:
            info["cpu_core_count"] = psutil.cpu_count(logical=False)
    except:
        pass


def _cpuinfo(info):
    missing = _has_missing(info, CPUINFO_MAPPING)
    if not missing:
        return

    try:
        import cpuinfo

        cpu_info = cpuinfo.get_cpu_info()
        _fill_from_cpuinfo(info, cpu_info)
    except:
        pass


def _lscpu(info):
    missing = _has_missing(info, LSCPU_MAPPING)
    if not missing:
        return

    try:
        command = ["lscpu", "--bytes"]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            return
    except:
        return

    parts = result.stdout.decode("utf-8").strip().split("\n")
    _fill_from_lscpu(info, parts)


def _meminfo(info):
    missing = _has_missing(info, MEMINFO_MAPPING)
    if not missing:
        return

    try:
        command = ["cat", "/proc/meminfo"]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            return
    except:
        return

    parts = result.stdout.decode("utf-8").strip().split("\n")
    _fill_from_meminfo(info, parts)


def _nvidia_smi(info):
    missing = _has_missing(info, NVIDIA_SMI_MAPPING)
    if not missing:
        return

    try:
        command = ["nvidia-smi", "--query-gpu=gpu_name", "--format=csv,noheader"]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            return
    except:
        return

    parts = result.stdout.decode("utf-8").strip().split("\n")
    if parts:
        info["gpu_count"] = len(parts)
        info["gpu_product_names"] = parts


def _fill_from_cpuinfo(info, cpu_info):
    for key, lookup in CPUINFO_MAPPING.items():
        if lookup not in cpu_info:
            continue
        try:
            if not info[key]:
                if key == "cpu_model_name":
                    info[key] = cpu_info[lookup]
                else:
                    value = str(cpu_info[lookup])
                    parts = value.split(" ")
                    if len(parts) == 1:
                        info[key] = int(float(value))
                    elif len(parts) == 2:
                        value, unit = parts
                        value = int(float(value))
                        if unit == "KiB":
                            info[key] = value * 1024
                        elif unit == "MiB":
                            info[key] = value * 1024 * 1024
        except ValueError:
            pass


def _fill_from_lscpu(info, parts):
    lscpu_dict = {}
    for part in parts:
        x = part.split(":")
        if len(x) == 2:
            k, v = x
            lscpu_dict[k.strip()] = v.strip()

    for key, lookup in LSCPU_MAPPING.items():
        if lookup not in lscpu_dict:
            continue
        try:
            if not info[key]:
                if lookup.endswith("MHz"):
                    info[key] = int(float(lscpu_dict[lookup]) * 10**6)
                elif key in MUST_BE_INTS:
                    # lscpu sometimes includes descriptions after the value so remove that
                    info[key] = int(float(lscpu_dict[lookup].split(maxsplit=1)[0]))
                else:
                    info[key] = lscpu_dict[lookup]
        except ValueError:
            pass


def _fill_from_meminfo(info, parts):
    meminfo_dict = {}
    for part in parts:
        x = part.split(":")
        if len(x) == 2:
            k, v = x
            meminfo_dict[k.strip()] = v.strip().split(" ")[0]

    for key, lookup in MEMINFO_MAPPING.items():
        if lookup not in meminfo_dict:
            continue
        try:
            if not info[key]:
                info[key] = int(float(meminfo_dict[lookup]) * 1000)
        except ValueError:
            pass


def _has_missing(info, mapping):
    for key in mapping:
        if not info[key]:
            return True
    return False


def _exec_command(command):
    result = subprocess.run(command, capture_output=True)
    return result.stdout.decode("utf-8").strip()
