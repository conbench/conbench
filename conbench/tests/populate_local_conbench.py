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
    log.info("start create_benchmarks_data()")
    create_benchmarks_data()
    log.info("start create_benchmarks_data()")
    create_benchmarks_data_with_history()
    log.info("start generate_synthetic_benchmark_history()")
    generate_synthetic_benchmark_history()


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
    if r.text and "Email address already in use" in r.text:
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


def create_benchmarks_data_with_history():
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
    commits = [
        c.strip()
        for c in reversed(ARROW_COMMIT_HASH_LINES_50.splitlines())
        if c.strip()
    ]
    benchmark_name = "dummy-bench"

    distr_mean = 20.0
    # `lower_bound` is to simulate the real-world effect of there being a
    # theoretical optimum: the fastest benchmark duration time with all sources
    # of noise being silenced.
    lower_bound = 17.5
    slowdown_offset = distr_mean * 0.1
    slowdown_lin = distr_mean * 0.1
    distribution = statistics.NormalDist(mu=20.0, sigma=2)

    # Collect benchmark IDs as returned by the Conbench API after submission.
    benchmark_ids = []

    def sample_slowdown(s):
        # "slowdown" refers to the idea that the individual number has a time
        # unit (measuring a duration) and that a certain benchmark result was
        # affected by a more or less significant slowdown effect, increasing
        # this sample's duration.
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

        # Set (overwrite) duration / stats property. Generate with statistical
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
50 commits of apache/arrow walking backwards from 85b167c0. Obtained with
this command:

git log --pretty=%P -n 50 85b167c05c2f93a95b23e8ac4fd4da576ea5b899

If in the future we want to do e.g. every 20th commit in the apache/arrow
repository, one could do:

git log --pretty=%P -n 1000 85b167c05c2f93a95b23e8ac4fd4da576ea5b899 | awk
'NR%20<1'

Not done right now to easen CI's usage of the GitHub HTTP API and to keep the
time-to-comletion of `make db-populate` lowish.
"""
ARROW_COMMIT_HASH_LINES_50 = """
    33d677c480ab8aa841e4dc8dbffeb4cd40a00731
    7e02fde6527720f5e859b3c27036661f8e5ad03d
    92895c9b54dce55637191e15f83de34a60c9e5ab
    154de48f0b6c16ae5acc384ed8383704253afd96
    5f3df1255e6e0b7d2d4e197afec447769335f087
    0121ae73f4852ee3c5a6870ed5583916662a35be
    11d286eafb72b630baf897e619c84ecdfc6b723f
    4d31b1ef70be330356ed9119f63931f8fd90e6d1
    878d5cac09073cee72de000a7e8418ce8a3a31b8
    211925c92ecb0cd5d69b518481bcd6f60075864f
    37f5a3584aa44a919d3a620c7f2b4ad7e56c97c7
    2acc51a7d5304c3fc6a432f1c09946547ca91d74
    686610374ca52b39354df668a66e5fd4103b86d7
    c32b45e3b7b8dd2fdec8fa2bdf65b36eff7016b9
    385331185ac96b5a20a81b2c5de82158a2641af8
    3f31b327cd04e79e673b37ee684d438a72367483
    21d6374d2579c07d75832c5baf06479898e82fd5
    14ec80f182532b960cd4b5d1e72bcad04ba651da
    a580f2711750ef507cc57ce48cb431dd700a6166
    6bd847b2aefdb0f10eaf83a3bfe2dc8ee269e8e4
    d2481a610f7653e1b965366461dd6be0c22c1fda
    1e4a9914c191eeb0f2415a3bd0b92022647ce93d
    9fcaa38250d0d7bd59b5fc369a7757e357cf26ca
    5fce7618b81b6e42fc1331ab49b8fdf6b73de22f
    d4a0c9e8be8f2730dd80be9934e27aa6bd4a0850
    040310fe853ca7675e67ba47533087070a6e7ed3
    25b50932cdf7e8b9b259608b27884ff3d7b90444
    773b5d815c8dd68a4ff1e3b90f7838ab770a9d27
    2410d36773d04ebe1b13a54748a947eed6fb304e
    e5ec942075b079964955729761095547f5ff2a70
    c6eb4aad30280e1df269f526de057a479c5bc68a
    c45ce8102eaafb09a02b8638028f62bd01f6a150
    53d73f8f97516443cdcf98f71c0cbc527dae7dc4
    ec9a8a322b9486584e51c174b63774fd496783b0
    4dd5cedb21d7b58d837bdb3c0d35a5cd80fd9f4b
    44bd06d84c10a4ca8c2c9c8fb044ab7620b9de47
    8ed4513cecc066148ac782cc5bb94738e51318ad
    ceec7950e8c6e9a63f48d27c284c56938df3598d
    793e5f6251255cfe812f4f187f2924224fefad8b
    63b91cc1f7131356537ab9cbb84ed108d6f9102e
    139a13e320b9a47161ff506c90c5facaec8b773c
    f4ed8185ebc1804092de46e58078414910587958
    240ebb75b57bb05551c9103ec3dee11c23fd0aca
    4a40a8294ed39c48dc9fb7f99f05de2e8d1ecd2e
    5bbcf40bbc47608b5a09fc71ec16d23368af1ab1
    31237a6c661e0077d3873ec7437af4828b25f485
    b1a48c78a318402daab1d0f974825373ef41b293
    1aa8f3554781de81630f3a334e146a73177a2fa3
    91e1a98c7f2751deb1ff76a1a3e1a87b094c5684
    1e8ca94fc3682eb97bcf243545dcb282c1aaa0b4
    """


if __name__ == "__main__":
    main()
