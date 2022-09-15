import abc
import copy
import gc
import multiprocessing as mp
import subprocess
import time
import warnings

from benchadapt import BenchmarkResult


class CacheManager:
    _drop_failed = False
    _purge_failed = False

    def sync_and_drop(self):
        if not self._drop_failed:
            command = "sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"
            try:
                subprocess.run(command, shell=True, check=True)
                return True
            except subprocess.CalledProcessError:
                self._drop_failed = True

        if not self._purge_failed:
            command = "sync; sudo purge"
            try:
                subprocess.run(command, shell=True, check=True)
                return True
            except subprocess.CalledProcessError:
                self._purge_failed = True

        return False


class Iteration(abc.ABC):
    cache = None

    def __init__(self) -> None:
        self.cache = CacheManager()

    def setup(self, params: dict) -> dict:
        """
        Code to run in each iteration before timing. Results are passed to the
        ``setup_results`` param of ``iteration_run()``.
        """
        return {}

    @abc.abstractmethod
    def run(self, params: dict, setup_results: dict) -> dict:
        """Code to time. Results are passed to ``iteration_teardown()``"""

    def teardown(self, params: dict, run_results: dict) -> None:
        """Code to run in each iteration after timing"""
        pass

    def __call__(self, params: dict, settings: dict, queue: mp.Queue) -> float:
        if settings["drop_caches"]:
            self.cache.sync_and_drop()
        if settings["gc_collect"]:
            gc.collect()
        if settings["gc_disable"]:
            gc.disable()

        elapsed_time = None
        error = None
        try:
            setup_results = self.setup(params=params)
            start_time = time.time()
            run_results = self.run(params=params, setup_results=setup_results)
            end_time = time.time()
            self.teardown(params=params, run_results=run_results)
            elapsed_time = end_time - start_time
        except Exception as e:
            error = repr(e)
            warnings.warn(error)

        gc.enable()

        queue.put({"time": elapsed_time, "error": error})
        return elapsed_time


class Benchmark:
    """
    An abstract class defining the bits required for running a benchmark
    """

    iteration = None
    settings = None
    cache = None

    def __init__(
        self,
        iteration: Iteration,
        drop_caches: bool = False,
        gc_collect: bool = True,
        gc_disable: bool = True,
    ) -> None:
        self.iteration = iteration
        self.settings = {
            "drop_caches": drop_caches,
            "gc_collect": gc_collect,
            "gc_disable": gc_disable,
        }

        self.cache = CacheManager()

    def run_iteration(self, params: dict) -> dict:
        iteration = copy.deepcopy(self.iteration)
        queue = mp.Queue()
        proc = mp.Process(target=iteration, args=(params, self.settings, queue))
        proc.start()
        res = queue.get()
        proc.join()
        return res

    def run_case(self, params: dict, iterations: int = 1) -> BenchmarkResult:

        times = []
        error = None
        for _ in range(iterations):
            res = self.run_iteration(params=params)
            if res["error"]:
                error = res["error"]
            else:
                times.append(res["time"])

        if len(times) > 0:
            stats = {"data": times, "units": "s"}
        else:
            stats = None

        res = BenchmarkResult(
            stats=stats,
            error=error,
            context={"benchmark_language": "Python"},
        )

        return res


import pyarrow as pa
import pyarrow.parquet as pq


class MyIteration(Iteration):
    def setup(self, params: dict) -> dict:
        df = pq.read_table("/Users/alistaire/data/benchmarks/data/nation_1.parquet")
        return {"df": df}

    def run(self, params: dict, setup_results: dict) -> float:
        ar = setup_results["df"]["n_regionkey"].chunk(0)
        sc = pa.scalar(params["x"], pa.int32())
        return pa.compute.add(ar, sc) + 1


if __name__ == "__main__":
    import json

    my_bm = Benchmark(iteration=MyIteration())
    bm_res = my_bm.run_case(params={"x": 2}, iterations=3)
    print(json.dumps(bm_res.to_publishable_dict(), indent=2))
