import logging
import os
import queue
import time
from threading import Thread

import requests

log = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(threadName)s: %(message)s",
    datefmt="%y%m%d-%H:%M:%S",
)


# base_url = "http://127.0.0.1:8000/api"
# if os.environ.get("CONBENCH_BASE_URL"):
base_url = f"{os.environ['CONBENCH_BASE_URL']}"


session = requests.Session()

targets = [
    ("/api/ping/", "GET", 2.0),
    ("/", "GET", 2.0),
    ("/runs/7838-426c-88c1-01d854d8ee72/", "GET", 0.5),
    (
        "compare/benchmarks/fd773f3414b04ca783c97925fe05c2c5...40872ceb41094f1ea509b19ccb762fb8/",
        "GET",
        0.2,
    ),
    ("/batches/0d32f00ea4884aaea10454cf61f7e91f/", "GET", 0.1),
    ("/benchmarks/4a175cbb62cb473389e78174e5dc9991/", "GET", 0.1),
    ("/benchmarks/35b0b18277a24bbda262ecd66bf5ad42/", "GET", 0.5),
    ("/login/", "GET", 0.05),
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
    t_consumers = [Thread(target=task_consumer) for _ in range(2)]

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

    log.info("making request")

    methodstring = target[1]
    url = base_url + target[0]
    try:
        reqmethod_str_map[methodstring](url, timeout=(1.05, 5))
        HTTP_REQUESTS_MADE_COUNTER += 1
    except requests.exceptions.RequestException as exc:
        log.info("request %s failed with %s", target, exc)


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


if __name__ == "__main__":
    main()
