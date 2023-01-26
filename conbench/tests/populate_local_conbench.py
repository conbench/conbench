import datetime
import logging
import os
import random
import statistics
import time
import uuid

import requests

log = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
    datefmt="%y%m%d-%H:%M:%S",
)


base_url = "http://127.0.0.1:5000/api"
if os.environ.get("CONBENCH_BASE_URL"):
    base_url = f"{os.environ.get('CONBENCH_BASE_URL')}/api"


session = requests.Session()


def main():
    register()
    login()
    log.info("start generate_synthetic_benchmark_history()")
    generate_synthetic_benchmark_history()
    log.info("start create_benchmarks_data()")
    create_benchmarks_data()
    log.info("start create_benchmarks_data()")
    create_benchmars_data_with_history()


def generate_benchmarks_data(
    run_id,
    commit,
    branch,
    benchmark_name,
    benchmark_language,
    timestamp,
    hardware_type,
    reason,
    mean=16.670462,
):
    """
    Generate a dictionary that complies with the BenchmarkCreate schema.
    """
    run_name = f"{reason}: {commit}" if reason else commit
    data = {
        "batch_id": uuid.uuid4().hex,
        "context": {
            "arrow_compiler_flags": "-fvisibility-inlines-hidden -std=c++17 -fmessage-length=0 -march=nocona -mtune=haswell -ftree-vectorize -fPIC -fstack-protector-strong -fno-plt -O2 -ffunction-sections -pipe -isystem /var/lib/buildkite-agent/miniconda3/envs/arrow-commit/include -fdiagnostics-color=always -O3 -DNDEBUG",
            "benchmark_language": benchmark_language,
        },
        "github": {
            "commit": commit,
            "repository": "https://github.com/apache/arrow",
            "branch": branch,
        },
        "info": {
            "arrow_compiler_id": "GNU",
            "arrow_compiler_version": "9.4.0",
            "arrow_version": "8.0.0-SNAPSHOT",
            "benchmark_language_version": "Python 3.8.12",
        },
        "run_id": str(run_id),
        "run_name": run_name,
        "stats": {
            "data": ["14.928533", "14.551965", "14.530887"],
            "iqr": "0.198823",
            "iterations": 3,
            "max": "14.928533",
            "mean": mean,
            "median": "16.551965",
            "min": "14.530887",
            "q1": "14.541426",
            "q3": "14.740249",
            "stdev": "0.223744",
            "time_unit": "s",
            "times": [],
            "unit": "s",
        },
        "tags": {
            "compression": "uncompressed1",
            "cpu_count": None,
            "dataset": "fanniemae_2016Q4",
            "name": benchmark_name,
            "streaming": "streaming",
        },
        "timestamp": str(timestamp),
        "validation": {"type": "pandas.testing", "success": True},
    }

    if reason:
        data["run_reason"] = reason

    data["optional_benchmark_info"] = {
        "log uri": "s3://some/log",
        "log url": "https://some/log",
        "trace uri": "s3://some/trace",
    }

    for key in ["info", "tags", "context"]:
        fields_set = {
            f"{benchmark_language}_specific_{key}_field_1": "value-1",
            f"{benchmark_language}_specific_{key}_field_2": f"{benchmark_language}-{key}-value-2",
            f"{key}_field_3": f"{benchmark_language}-{key}-value-2",
            f"{key}_field_4": None if benchmark_language == "Python" else "value-4",
        }
        data[key].update(fields_set)
        if benchmark_language == "Python":
            for i in range(5, 7):
                data[key][f"field_{i}"] = f"value-{i}"

    if hardware_type == "cluster":
        data["cluster_info"] = {
            "name": "cluster1",
            "info": {"workers": 2, "scheduler": 1},
            "optional_info": {},
        }
    else:
        data["machine_info"] = {
            "name": "machine1",
            "architecture_name": "aarch64",
            "cpu_core_count": "16",
            "cpu_frequency_max_hz": "0",
            "cpu_l1d_cache_bytes": "65536",
            "cpu_l1i_cache_bytes": "65536",
            "cpu_l2_cache_bytes": "1048576",
            "cpu_l3_cache_bytes": "33554432",
            "cpu_model_name": "",
            "cpu_thread_count": "16",
            "gpu_count": "0",
            "gpu_product_names": [],
            "kernel_name": "4.14.248-189.473.amzn2.aarch64",
            "memory_bytes": "64424509440",
            "os_name": "Linux",
            "os_version": "4.14.248-189.473.amzn2.aarch64-aarch64-with-glibc2.17",
        }

    return data


def generate_benchmarks_data_with_error(
    run_id,
    commit,
    branch,
    benchmark_name,
    benchmark_language,
    timestamp,
    hardware_type,
    reason,
):
    data = generate_benchmarks_data(
        run_id,
        commit,
        branch,
        benchmark_name,
        benchmark_language,
        timestamp,
        hardware_type,
        reason,
    )
    data.pop("stats")
    data["error"] = {"command": "some command", "stack trace": "stack trace ..."}
    return data


def generate_benchmarks_data_with_iteration_missing(
    run_id,
    commit,
    branch,
    benchmark_name,
    benchmark_language,
    timestamp,
    hardware_type,
    reason,
    with_error=True,
):
    data = generate_benchmarks_data(
        run_id,
        commit,
        branch,
        benchmark_name,
        benchmark_language,
        timestamp,
        hardware_type,
        reason,
    )
    stats = data.pop("stats")

    # mark the middle iteration as failed
    stats["data"] = [stats["data"][0], None, stats["data"][2]]

    # remove all the calculated stats details
    for key in ["iqr", "max", "mean", "median", "min", "q1", "q3", "stdev"]:
        stats.pop(key, None)

    data["stats"] = stats
    if with_error:
        data["error"] = {"command": "some command", "stack trace": "stack trace ..."}
    return data


def register():

    url = f"{base_url}/register/"
    log.info("register via: %s", url)

    data = {
        "email": "e@e.com",
        "password": "test",
        "name": "e",
        "secret": "innocent-registration-key",
    }
    r = session.post(url, json=data)
    if r.text and "Email address already in use":
        return

    assert str(r.status_code).startswith("2"), f"register failed:\n{r.text}"


def login():
    url = f"{base_url}/login/"
    log.info("login via: %s", url)

    data = {"email": "e@e.com", "password": "test", "remember_me": True}
    r = session.post(url, json=data)
    assert str(r.status_code).startswith("2"), f"login failed:\n{r.text}"
    log.info("login succeeded")


def post_benchmark_result(data):
    """
    Expect `data` to be a single BenchmarkCreate structure.

    Return benchmark ID (as returned by API) or raise an exception
    (the code below may fail with wild exceptions such as AttributeError)
    """

    url = f"{base_url}/benchmarks/"

    for attempt in range(1, 4):
        t0 = time.monotonic()
        log.info("POST to url: %s", url)
        try:
            # Often seeing RemoteDisconnected when the processing
            # takes too long. Also see
            # https://github.com/conbench/conbench/issues/555
            res = session.post(url, json=data)
            benchmark_id = res.json()["id"]
            break
        except requests.exceptions.RequestException as exc:
            log.info(
                "attempt %s failed with %s after %.5f",
                attempt,
                exc,
                time.monotonic() - t0,
            )
            time.sleep(5 * attempt)

    log.info(
        f"Posted a benchmark with run_id '{data.get('run_id')}' "
        f"and commit {data.get('github', {}).get('commit')}. "
        f"Received status code {res.status_code}. "
        f"Took {attempt} attempt(s). Last attempt took {time.monotonic() - t0 :.5f} s."
    )

    if str(res.status_code).startswith("4"):
        log.info("4xx response body: %s", res.text)

    return benchmark_id


def update_run(run_id, data):
    url = f"{base_url}/runs/{run_id}/"
    log.info(session.put(url, json=data))


def update_run_with_info(run_id, timestamp):
    data = {
        "finished_timestamp": str(timestamp + datetime.timedelta(hours=1)),
        "info": {"setup": "passed"},
        "error_info": {"error": "error", "stack_trace": "stack_trace", "fatal": True},
        "error_type": "fatal",
    }
    update_run(run_id, data)


def create_benchmarks_data():
    commits = [
        "e314d8d0d611c7f9ca7f2fbee174fcea3d0c66f2",
        "ce46c1adf10654248b02c349210bb63ecc6828ad",
        "9719eae66dcf38c966ae769215d27020a6dd5550",
        "650f111b524fb1c5bfbfa6f533d15929c90ddc40",
        "e26a88fd9fecca876073c5a18cf571c0daca6b3b",
        "2462492389a8f2ca286c481852c84ba1f0d0eff9",
    ]

    branches = ["apache:master", None] * 3

    means = [16.670462, 16.4, 16.5, 16.67, 16.7, 16.7]

    errors = [False, False, True, False, True, True]

    reasons = ["commit", None, "pull request", "nightly", "manual", "an accident"]

    benchmark_names = ["csv-read", "csv-write"]

    benchmark_languages = ["Python", "R", "JavaScript"]

    hardware_types = ["machine", "cluster"]

    runs = []

    for i in range(len(commits)):
        for hardware_type in hardware_types:
            for benchmark_language in benchmark_languages:
                for benchmark_name in benchmark_names:
                    run_id = f"{hardware_type}{i+1}"
                    commit, branch = commits[i], branches[i]
                    mean, reason = means[i], reasons[i]
                    timestamp = datetime.datetime.now() + datetime.timedelta(hours=i)
                    if errors[i] and benchmark_name == "csv-read":
                        benchmark_data = generate_benchmarks_data_with_error(
                            run_id,
                            commit,
                            branch,
                            benchmark_name,
                            benchmark_language,
                            timestamp,
                            hardware_type,
                            reason,
                        )
                    else:
                        benchmark_data = generate_benchmarks_data(
                            run_id,
                            commit,
                            branch,
                            benchmark_name,
                            benchmark_language,
                            timestamp,
                            hardware_type,
                            reason,
                            mean,
                        )

                    # Is this actually posting _one_ benchmark result or
                    # more than one? The function name suggests plural.
                    post_benchmark_result(benchmark_data)
                    runs.append((run_id, timestamp))

    run_id, timestamp = runs[-1]
    update_run_with_info(run_id, timestamp)


def create_benchmars_data_with_history():
    # 7 commits in a row in apache/arrow, the commented one is missing
    commits = [
        "17d6fdc0e9c00534e4de7bfb193c33c86cab7e15",
        # "3a1ec998539cd6da1bccb7f06e68448846b6e318",
        "a2114c0605be66bb16d16ee0b25c9d81ab68f5ce",
        "cab3e216e17ce8422a15f91480bb408a052b578c",
        "d404c9c6a0d6ce94f054596e667205995ef944d2",
        "73cdd6a59b52781cc43e097ccd63ac36f705ee2e",
        "88b42ef66fe664043c5ee5274b2982a3858b414e",
    ]

    means = [16.5, 16.670462, 16.4, 16.5, 16.67, 16.7]

    benchmark_names = ["csv-read", "csv-write"]

    partial_successes = [False, True]

    runs = []

    benchmark_ids = []

    i = 0
    n = 0
    for commit in commits:
        mean = means[i]
        i += 1
        for partial_success in partial_successes:
            n += 1
            run_id = f"history_machine{n}"

            for benchmark_name in benchmark_names:
                timestamp = datetime.datetime.now() + datetime.timedelta(hours=i)
                if partial_success:
                    benchmark_data = generate_benchmarks_data_with_iteration_missing(
                        run_id,
                        commit,
                        None,
                        benchmark_name,
                        "Python",
                        timestamp,
                        "machine",
                        reason="commit",
                        # in order to see the auto-populating of errors on partial completes
                        with_error=True if benchmark_name == "csv-read" else False,
                    )
                else:
                    benchmark_data = generate_benchmarks_data(
                        run_id,
                        commit,
                        None,
                        benchmark_name,
                        "Python",
                        timestamp,
                        "machine",
                        reason="commit",
                        mean=mean,
                    )

                benchmark_id = post_benchmark_result(benchmark_data)
                benchmark_ids.append(benchmark_id)
                runs.append((run_id, timestamp))


def generate_synthetic_benchmark_history():

    commits = [c.strip() for c in reversed(ARROW_COMMIT_HASH_LINES_50.splitlines())]
    benchmark_name = "dummy-bench"

    distr_mean = 20.0
    # This is to simulate the real-world effect of there being a theoretical
    # optimum: the fastest benchmark duration time with all sources of noise
    # being silenced.
    lower_bound = 17.5
    slowdown_offset = distr_mean * 0.1
    slowdown_lin = distr_mean * 0.1
    distribution = statistics.NormalDist(mu=20.0, sigma=2)

    benchmark_ids = []

    def sample_slowdown(s):
        return s + slowdown_offset + slowdown_lin * random.random()

    for idx, commit_hash in enumerate(commits, 1):

        # Get current time as tzaware datetime object in UTC timezone, and
        # then subtract
        run_start = datetime.datetime.utcnow().replace(
            tzinfo=datetime.timezone.utc
        ) - datetime.timedelta(hours=10 * idx)
        run_start_timestring_iso8601 = run_start.isoformat()

        # Submit a BenchmarkCreate structure. Use a random run_id so that
        # each benchmark created in this loop refers to a different run.
        bdata = generate_benchmarks_data(
            run_id=str(uuid.uuid4())[9:],
            commit=commit_hash,
            branch=None,
            benchmark_name=benchmark_name,
            benchmark_language="Dumython",
            timestamp=run_start_timestring_iso8601,
            hardware_type="dummymachine",
            reason="commit",
            mean=None,
        )

        # Overwrite duration / stats property. Generate with statistical
        # properties.
        bdata["stats"] = None

        # Implement lower bound. Better: choose a different distribution, not
        # a normal distribution.
        samples = []
        while len(samples) < 6:
            s = distribution.samples(n=1)[0]
            if s < lower_bound:
                continue
            samples.append(s)

        # Simulate for this complete set of iterations to have been affected by
        # a slowdown.
        if random.random() < 0.1:
            # Shift all samples a little higher (not by the same amount)
            samples = [sample_slowdown(s) for s in samples]

        # Simulate for any sample to have been affected by some blip-slowdown
        if random.random() < 0.02:
            # Shift a specific, random sample a little higher
            rndidx = random.randint(0, len(samples) - 1)
            samples[rndidx] = sample_slowdown(samples[rndidx])

        bdata["stats"] = {
            "data": [str(s) for s in samples],
            "iterations": len(samples),
            "unit": "s",
            "time_unit": "s",
            "times": [],
        }

        benchmark_ids.append(post_benchmark_result(bdata))

    log.info("now, emit a benchmark ID on stdout")
    # That benchmark ID is consumed and used by CI.
    print(benchmark_ids[0])


"""
Every 20th commit in the apache/arrow repository, walking the commit tree
backwards by 1000 commits, starting at commit 85b167c05. Done with the
following command:

git log --pretty=%P -n 1000 85b167c05c2f93a95b23e8ac4fd4da576ea5b899 | awk 'NR%20<1'
"""
ARROW_COMMIT_HASH_LINES_50 = """
    6bd847b2aefdb0f10eaf83a3bfe2dc8ee269e8e4
    63b91cc1f7131356537ab9cbb84ed108d6f9102e
    d00f016315408d653b2a46d3fd8922616264ced4
    5a9805807456fa1b50671afded557044ab6cc8e6
    4e9158d373df105f01ba9d6052cfb9ab7ecdcbeb
    676c804de55bae97e5060e16e650565de163a8fe
    b21bf749f291367f85ad61751205e7deeee92bc7
    53c659ae4de8d6b9194cd9f410c078c136a274d2
    26a426f325256e260a15521d5097efffd2f1ceb1
    8a8999e94038aa9a60d3ac15741cf9c7abad0433
    fde7b937c84eaad842ab0457d2490c6c8c244697
    fb29effbb689014ea50f8bf3814539d5cc8f7021
    57b81cac8a5d9dfa56c8a224cb2bc9b9046fb807
    e0e7ba824f56460cdb7dd9ffa6779de93b62d121
    dab5d3a29394f59045ac6b66f9b697507d6cd1b7
    3da803db456536782e6ad1cd6cb4f5d08d6a5d6a
    619b034bd3e14937fa5d12f8e86fa83e7444b886
    b41bd80187d88f5187a3dc7c42444fbbcca6f7a8
    4e7d91cd7ad42c10195ef465f5b6f1daf7b72f05
    7f6c5aeb5388936709642e48aed6419d1e2144a6
    2f627c213fc328ca7cd058d4455581fc246837da
    ebda85fcb7bc422427a85ff50fa39551cbd6a41f
    aeba61663fdd82719e6cc0945aba216958ad6970
    6bf9a546f296cdeebfe5cc543e1d1351cf251509
    20626f833be5c1241161054665ccc3906f3da1c3
    49a53d2fe01145ade49e4af68092af1b73570f9c
    13ede7bb17992e5afe65daf38006b891c47d918a
    776626e56b07a3ba69f73b9f75bbc9d4f7fa72b7
    949e99af5f62ec68b41ce43ec079b1b49c6533e7
    7a568468119a1a530a8a45d5e66b72c8be807b0f
    b2871bb4d80695723f8a5ef54c864d9545e6b175
    58be6a317ff09eefb53c3f0122e4d4eedd166977
    529f653dfa58887522af06028e5c32e8dd1a14ea
    b48d2287bef95ed195f6e3721dd34f97fd1735c2
    29225accecb74b4974920a8acaca55578a44254e
    9d6598108c4fd93be89f8f5becaa7cb66f929fe7
    df121b7feec92464a4e97fe535a864537a16be1b
    fea7cc3a5992622731fd86989b6d87998a79eb6e
    93b63e8f3b4880927ccbd5522c967df79e926cda
    04d240318555f5b0207b4deee233f3d36ad4c6fe
    5f84335fbb1e1467eed07563be00e9338a06ff03
    f0688d01c465417e6f3515f9344154ad6f47ba22
    bc1a16cd0eceeffe67893a7e8000d2dd28dcf3f1
    838687178fda7f82e31668f502e2f94071ce8077
    6d575b621d14c4b48558da0d366ba007793b2d0c
    8cac69c809e2ae9d4ba9c10c7b22869c1fd11323
    036fdf2d03c3a6986109f053d94fc237d2c2f82d
    545b4313d6db2dfcc4ea0aa4ac23785d64450e1d
    ee2e9448c8565820ba38a2df9e44ab6055e5df1d
    9c422a2011404ee0c5c01eeb2a6a1d5333816cad

    82ba27906c88ef5e5b1b684938f10cbb817edceb
    """


if __name__ == "__main__":
    main()
