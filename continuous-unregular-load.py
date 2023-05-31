import datetime
import logging
import os
import queue
import time
import uuid
from threading import Thread

import random

import requests

log = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(threadName)s: %(message)s",
    datefmt="%y%m%d-%H:%M:%S",
)

RANDOM_RUN_IDS = [uuid.uuid4().hex for _ in range(10)]


# base_url = "http://127.0.0.1:8000/api"
# if os.environ.get("CONBENCH_BASE_URL"):
base_url = f"{os.environ['CONBENCH_BASE_URL']}"


session = requests.Session()

# The number is the desired target rate, in 1/s.

targets = [
    # ("/api/ping/", "GET", 0.5),
    # ("/", "GET", 1.0),
    # (f"/runs/{RANDOM_RUN_IDS[0]}/", "GET", 0.1),
    # (f"/api/compare/runs/{RANDOM_RUN_IDS[0]}...{RANDOM_RUN_IDS[3]}/", "GET", 1.0),
    ("/api/benchmark-results/", "POST", 10.0),
    # (
    #     "/compare/benchmarks/fd773f3414b04ca783c97925fe05c2c5...40872ceb41094f1ea509b19ccb762fb8/",
    #     "GET",
    #     0.2,
    # ),
    # ("/batches/0d32f00ea4884aaea10454cf61f7e91f/", "GET", 0.1),
    # ("/benchmarks/4a175cbb62cb473389e78174e5dc9991/", "GET", 0.1),
    # ("/benchmarks/35b0b18277a24bbda262ecd66bf5ad42/", "GET", 0.5),
    # ("/login/", "GET", 0.05),
]


process_launch_time = time.monotonic()
last_time_i_did_that = {}

# Large maxsize just to pre-pan for the fact that there might be a higher work
# creation rate than a fixed-size executor pool can process, and this case
# needs to be handled by code (back off, instead of having infinite memory
# usage growth).
q = queue.Queue(maxsize=1000)


INIT_SHUTDOWN = False

HTTP_REQUESTS_MADE_COUNTER = 0


def main():
    global INIT_SHUTDOWN

    register()
    login()

    # Start the task creator thread (infinite loop)
    t_creator = Thread(target=task_creator)
    t_creator.start()

    # Start N task consumer threads, each also running an infinite loop.
    t_consumers = [Thread(target=task_consumer) for _ in range(10)]

    for thread in t_consumers:
        thread.start()

    # main thread, hang out a bit.
    while True:
        log.debug("main thread: bored.. hello")

        if (HTTP_REQUESTS_MADE_COUNTER % 50) == 0:
            log.info("HTTP requests made so far: %s", HTTP_REQUESTS_MADE_COUNTER)

        try:
            time.sleep(0.2)
        except KeyboardInterrupt:
            log.info("caught SIGINT, initiate shutdown")
            INIT_SHUTDOWN = True
            break

    log.info("joining creator thread")
    t_creator.join()

    for thread in t_consumers:
        log.info("joining consumer thread %s", thread)
        thread.join()


def task_consumer():
    while True:
        if INIT_SHUTDOWN:
            log.info("consumer thread: exit")
            return
        _task_consumer_iteration()
        time.sleep(0.001)


def task_creator():
    while True:
        if INIT_SHUTDOWN:
            log.info("creator thread: exit")
            return

        _task_creator_iteration()
        time.sleep(0.01)


reqmethod_str_map = {"GET": session.get, "POST": session.post}


def _task_consumer_iteration():
    global HTTP_REQUESTS_MADE_COUNTER

    log.debug("consumer iteration")
    try:
        target = q.get(block=True, timeout=0.01)
    except queue.Empty:
        # log.info("thread did not have to do work")
        return

    # log.info("making request")

    methodstring = target[1]
    url = base_url + target[0]

    reqargs = {
        "url": url,
        "timeout": (1.05, 35),
    }

    if methodstring == "POST":
        # For now, POST implies: posting benchmark result
        reqargs["json"] = gen_bmresult()
    try:
        resp = reqmethod_str_map[methodstring](**reqargs)
        HTTP_REQUESTS_MADE_COUNTER += 1
    except requests.exceptions.RequestException as exc:
        log.info("request %s failed with %s", target, exc)
        # Response object is not defined. Error out.
        return

    if str(resp.status_code).startswith("4"):
        log.info(
            "request %s failed with resp: %s, %s", target, resp.status_code, resp.text
        )


def _task_creator_iteration():
    # log.info("creator iteration")
    for t in targets:
        last_time = last_time_i_did_that.get(t)
        if last_time is None:
            # Pretend as if we just did that at the time when the
            # process tarted.
            last_time = process_launch_time

        # So many seconds passed since we last did that.
        time_passed = time.monotonic() - last_time

        # Turn this into a rate, a candidate rate -- the current that if we
        # were to trigger this action ~now. Example: 10 s -> 0.1 Hz
        current_rate_candidate = 1.0 / time_passed

        target_rate = t[-1]

        # If the current rate candidate is lower than the target rate:
        # submit a task to do this.
        if current_rate_candidate < target_rate:
            try:
                q.put(t, block=True, timeout=0.1)
            except queue.Full:
                log.info("task creator: queue is full")
                return

            # Take not of task submission, not execution. This is so that we do
            # not accidentally submit this too often (if consumers are slow)
            last_time_i_did_that[t] = time.monotonic()


def register():
    url = f"{base_url}/api/register/"
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
    url = f"{base_url}/api/login/"
    log.info("login via: %s", url)
    data = {"email": "e@e.com", "password": "test"}
    r = session.post(url, json=data, timeout=(3, 5))
    assert str(r.status_code).startswith("2"), f"login failed:\n{r.text}"
    log.info("login succeeded")


def gen_bmresult():
    """
    Generate dictionary that complies with the BenchmarkResultCreate schema.
    """

    benchmark_name = "fozzelbenchmark"
    return {
        "context": {
            "arrow_compiler_flags": "-fvisibility-inlines-hidden",
            "benchmark_language": "yes",
        },
        "github": {
            "commit": "4d31b1ef70be330356ed9119f63931f8fd90e6d1",
            "repository": "https://github.com/apache/arrow",
        },
        "info": {
            "arrow_compiler_id": "GNU",
            "arrow_compiler_version": "9.4.0",
        },
        "batch_id": "foo",  # why is that required?
        "run_id": random.choice(RANDOM_RUN_IDS),
        "run_name": "rname",
        "stats": {
            "data": [1.1111, 2.22222, 3.33333],
            "iterations": 3,
            "time_unit": "s",
            "times": [],
            "unit": "s",
        },
        "tags": {
            "compression": random.choice(["a", "b", "c"]),
            "name": benchmark_name,
        },
        "timestamp": str(datetime.datetime.now() - datetime.timedelta(hours=3)),
        "validation": {"type": "pandas.testing", "success": True},
        "machine_info": {
            # Some projects set massive machine names. See how the UI deals
            # with that.
            "name": "3wrn5-lf0jw",
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
        },
    }


if __name__ == "__main__":
    main()
