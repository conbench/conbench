<p align="right">
<a href="https://github.com/ursacomputing/conbench/blob/main/.github/workflows/actions.yml"><img alt="Build Status" src="https://github.com/ursacomputing/conbench/actions/workflows/actions.yml/badge.svg?branch=main"></a>
<a href="https://coveralls.io/github/ursacomputing/conbench?branch=main"><img src="https://coveralls.io/repos/github/ursacomputing/conbench/badge.svg?branch=main&kill_cache=06b9891a46827df564072ae831b13897599f7f3d" alt="Coverage Status" /></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

# Conbench


<img src="https://github.com/ursacomputing/conbench/blob/main/conbench.png" alt="Language-independent Continuous Benchmarking (CB) Framework">


Conbench allows you to write benchmarks in any language, publish the
results as JSON via an API, and persist them for comparison while
iterating on performance improvements or to guard against regressions.

Conbench includes a runner which can be used as a stand-alone library
for traditional benchmark authoring. The runner will time a unit of
work, collect machine information that may be relevant for hardware
specific optimizations, and return JSON formatted results.

You can optionally host a Conbench server (API & dashboard) to share
benchmark results more widely, explore the changes over time, and
compare results across varying benchmark machines, languages, and cases.

There is also a Conbench command line interface, useful for Continuous
Benchmarking (CB) orchestration alongside your development pipeline.


<p align="center">
    <img src="https://arrow.apache.org/img/arrow.png" alt="Apache Arrow" height="100">
</p>


The [Apache Arrow](https://arrow.apache.org/) project is using Conbench
for Continuous Benchmarking. They have both native Python Conbench
benchmarks, and Conbench benchmarks written in Python that know how to
execute their external C++ and R benchmarks and record those results
too. Those benchmarks can be found in the
[ursacomputing/benchmarks](https://github.com/ursacomputing/benchmarks)
repository, and the results are hosted on the
[Arrow Conbench Server](https://conbench.ursa.dev/).


- May 2021: https://ursalabs.org/blog/announcing-conbench/

<hr>


## Index

* [Contributing](https://github.com/ursacomputing/connbench#contributing)
* [Authoring benchmarks](https://github.com/ursacomputing/conbench#authoring-benchmarks)


## Contributing


### Create workspace
    $ cd
    $ mkdir -p envs
    $ mkdir -p workspace


### Create virualenv
    $ cd ~/envs
    $ python3 -m venv conbench
    $ source conbench/bin/activate


### Clone repo
    (conbench) $ cd ~/workspace/
    (conbench) $ git clone https://github.com/ursacomputing/conbench.git


### Install dependencies
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ pip install -r requirements-test.txt
    (conbench) $ pip install -r requirements-build.txt
    (conbench) $ pip install -r requirements-cli.txt
    (conbench) $ python setup.py develop


### Start postgres
    $ brew services start postgres


### Create databases
    $ psql
    # CREATE DATABASE conbench_test;
    # CREATE DATABASE conbench_prod;


### Launch app
    (conbench) $ flask run
     * Serving Flask app "api.py" (lazy loading)
     * Environment: development
     * Debug mode: on
     * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)


### Test app
    $ curl http://127.0.0.1:5000/api/ping/
    {
      "date": "Fri, 23 Oct 2020 03:09:58 UTC"
    }


### View API docs
    http://localhost:5000/api/docs/


### Run tests
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ pytest -vv conbench/tests/


### Format code (before committing)
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ git status
        modified: foo.py
    (conbench) $ black foo.py
        reformatted foo.py
    (conbench) $ git add foo.py


### Lint code (before committing)
    (qa) $ cd ~/workspace/benchmarks/
    (qa) $ flake8
    ./foo/bar/__init__.py:1:1: F401 'FooBar' imported but unused


### Generate coverage report
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ coverage run --source conbench -m pytest conbench/tests/
    (conbench) $ coverage report -m


### Test migrations with the database running using brew
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ brew services start postgres
    (conbench) $ dropdb conbench_prod
    (conbench) $ createdb conbench_prod
    (conbench) $ alembic upgrade head


### Test migrations with the database running as a docker container
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ brew services stop postgres
    (conbench) $ docker-compose down
    (conbench) $ docker-compose build
    (conbench) $ docker-compose run migration


### To autogenerate a migration
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ brew services start postgres
    (conbench) $ dropdb conbench_prod
    (conbench) $ createdb conbench_prod
    (conbench) $ git checkout main && git pull    
    (conbench) $ alembic upgrade head
    (conbench) $ git checkout your-branch
    (conbench) $ alembic revision --autogenerate -m "new"


## Authoring benchmarks

There are three main types of benchmarks: "simple benchmarks" that time the
execution of a unit of work, "external benchmarks" that just record benchmark
results that were obtained from some other benchmarking tool, and "case
benchmarks" which benchmark a unit of work under different scenarios.

Included in this repository are contrived, minimal examples of these different
kinds of benchmarks to be used as templates for benchmark authoring. These
example benchmarks and their tests can be found here:


* [_example_benchmarks.py](https://github.com/ursacomputing/conbench/blob/main/conbench/tests/benchmark/_example_benchmarks.py)
* [test_cli.py](https://github.com/ursacomputing/conbench/blob/main/conbench/tests/benchmark/test_runner.py)
* [test_runner.py](https://github.com/ursacomputing/conbench/blob/main/conbench/tests/benchmark/test_cli.py)


### Example simple benchmarks

A "simple benchmark" runs and records the execution time of a unit of work.

Implementation details: Note that this benchmark extends
`conbench.runner.Benchmark`, implements the minimum required `run()`
method, and registers itself with the `@conbench.runner.register_benchmark`
decorator.

```
@conbench.runner.register_benchmark
class SimpleBenchmark(conbench.runner.Benchmark):
    """Example simple benchmark.

    Usage: conbench addition [OPTIONS]

      Run addition benchmark.

    Options:
      --iterations INTEGER   [default: 1]
      --drop-caches BOOLEAN  [default: False]
      --gc-collect BOOLEAN   [default: True]
      --gc-disable BOOLEAN   [default: True]
      --show-result BOOLEAN  [default: True]
      --show-output BOOLEAN  [default: False]
      --run-id TEXT          Group executions together with a run id.
      --run-name TEXT        Name of run (commit, pull request, etc).
      --help                 Show this message and exit.
    """

    name = "addition"

    def __init__(self):
        self.conbench = conbench.runner.Conbench()

    def run(self, **kwargs):
        def func():
            return 1 + 1

        tags, context, github_info = {}, {}, {}  # user defined
        benchmark, output = self.conbench.benchmark(
            func,
            self.name,
            tags,
            context,
            github_info,
            kwargs,
        )
        self.conbench.publish(benchmark)
        yield benchmark, output
```

```
$ cd ~/workspace/conbench/conbench/tests/benchmark/
$ conbench addition

Benchmark result:
{
    "context": {
        "benchmark_language": "Python",
        "benchmark_language_version": "Python 3.9.2"
    },
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/apache/arrow"
    },
    "machine_info": {
        "architecture_name": "x86_64",
        "cpu_core_count": "2",
        "cpu_frequency_max_hz": "3500000000",
        "cpu_l1d_cache_bytes": "32768",
        "cpu_l1i_cache_bytes": "32768",
        "cpu_l2_cache_bytes": "262144",
        "cpu_l3_cache_bytes": "4194304",
        "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
        "cpu_thread_count": "4",
        "kernel_name": "20.5.0",
        "memory_bytes": "17179869184",
        "name": "machine-abc",
        "os_name": "macOS",
        "os_version": "10.16"
    },
    "stats": {
        "batch_id": "c7e5280e65d24ec19d64a7636cef1bd4",
        "data": [
            "0.000003"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000003",
        "mean": "0.000003",
        "median": "0.000003",
        "min": "0.000003",
        "q1": "0.000003",
        "q3": "0.000003",
        "run_id": "c7e5280e65d24ec19d64a7636cef1bd4",
        "stdev": 0,
        "time_unit": "s",
        "times": [],
        "timestamp": "2021-06-21T22:18:16.752993+00:00",
        "unit": "s"
    },
    "tags": {
        "name": "addition",
        "year": "2020"
    }
}

```


### Example external benchmarks

An "external benchmark" records results that were obtained from some other
benchmarking tool (like executing an R benchmarks from command line, parsing
the resulting JSON, and recording those results).

Implementation details: Note that the following benchmark sets
`external = True`, and calls `record()` rather than `benchmark()` as the
example above does.

```
@conbench.runner.register_benchmark
class ExternalBenchmark(conbench.runner.Benchmark):
    """Example benchmark that just records external results.

    Usage: conbench external [OPTIONS]

      Run external benchmark.

    Options:
      --iterations INTEGER   [default: 1]
      --drop-caches BOOLEAN  [default: False]
      --gc-collect BOOLEAN   [default: True]
      --gc-disable BOOLEAN   [default: True]
      --show-result BOOLEAN  [default: True]
      --show-output BOOLEAN  [default: False]
      --run-id TEXT          Group executions together with a run id.
      --run-name TEXT        Name of run (commit, pull request, etc).
      --help                 Show this message and exit.
    """

    external = True
    name = "external"

    def __init__(self):
        self.conbench = conbench.runner.Conbench()

    def run(self, **kwargs):
        # external results from somewhere
        # (an API call, command line execution, etc)
        result = {
            "data": [100, 200, 300],
            "unit": "i/s",
            "times": [0.100, 0.200, 0.300],
            "time_unit": "s",
        }

        tags, context, github_info = {}, {}, {}  # user defined
        benchmark, output = self.conbench.record(
            result,
            self.name,
            tags,
            context,
            github_info,
            kwargs,
            output=result["data"],
        )
        self.conbench.publish(benchmark)
        yield benchmark, output
```

```
$ cd ~/workspace/conbench/conbench/tests/benchmark/
$ conbench external

Benchmark result:
{
    "context": {
        "benchmark_language": "C++"
    },
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/apache/arrow"
    },
    "machine_info": {
        "architecture_name": "x86_64",
        "cpu_core_count": "2",
        "cpu_frequency_max_hz": "3500000000",
        "cpu_l1d_cache_bytes": "32768",
        "cpu_l1i_cache_bytes": "32768",
        "cpu_l2_cache_bytes": "262144",
        "cpu_l3_cache_bytes": "4194304",
        "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
        "cpu_thread_count": "4",
        "kernel_name": "20.5.0",
        "memory_bytes": "17179869184",
        "name": "machine-abc",
        "os_name": "macOS",
        "os_version": "10.16"
    },
    "stats": {
        "batch_id": "8058dde1491b49e5bd514646797c2a20",
        "data": [
            "100.000000",
            "200.000000",
            "300.000000"
        ],
        "iqr": "100.000000",
        "iterations": 3,
        "max": "300.000000",
        "mean": "200.000000",
        "median": "200.000000",
        "min": "100.000000",
        "q1": "150.000000",
        "q3": "250.000000",
        "run_id": "8058dde1491b49e5bd514646797c2a20",
        "stdev": "100.000000",
        "time_unit": "s",
        "times": [
            "0.100000",
            "0.200000",
            "0.300000"
        ],
        "timestamp": "2021-06-21T22:16:54.786499+00:00",
        "unit": "i/s"
    },
    "tags": {
        "name": "external",
        "year": "2020"
    }
}

```

### Example case benchmarks

A "case benchmark" is a either a "simple benchmark" or an "external benchmark"
executed under various predefined scenarios (cases).

Implementation details: Note that the following benchmark declares the valid
combinations in `valid_cases`, which reads like a CSV (the first row contains
the cases names). This benchmark example also accepts a data source argument
(see `arguments`), and additional `options` that are reflected in the resulting
command line interface.

```
@conbench.runner.register_benchmark
class CasesBenchmark(conbench.runner.Benchmark):
    """Example benchmark with cases, an option, and an argument.

    Usage: conbench subtraction [OPTIONS] SOURCE

      Run subtraction benchmark(s).

      For each benchmark option, the first option value is the default.

      Valid benchmark combinations:
      --color=pink --fruit=apple
      --color=yellow --fruit=apple
      --color=green --fruit=apple
      --color=yellow --fruit=orange
      --color=pink --fruit=orange

      To run all combinations:
      $ conbench subtraction --all=true

    Options:
      --color [green|pink|yellow]
      --fruit [apple|orange]
      --all BOOLEAN                [default: False]
      --count INTEGER              [default: 1]
      --iterations INTEGER         [default: 1]
      --drop-caches BOOLEAN        [default: False]
      --gc-collect BOOLEAN         [default: True]
      --gc-disable BOOLEAN         [default: True]
      --show-result BOOLEAN        [default: True]
      --show-output BOOLEAN        [default: False]
      --run-id TEXT                Group executions together with a run id.
      --run-name TEXT              Name of run (commit, pull request, etc).
      --help                       Show this message and exit.
    """

    name = "subtraction"
    valid_cases = (
        ("color", "fruit"),
        ("pink", "apple"),
        ("yellow", "apple"),
        ("green", "apple"),
        ("yellow", "orange"),
        ("pink", "orange"),
    )
    arguments = ["source"]
    options = {"count": {"default": 1, "type": int}}

    def __init__(self):
        self.conbench = conbench.runner.Conbench()

    def run(self, source, case=None, count=1, **kwargs):
        def func():
            return 100 - 1

        tags, context, github_info = {}, {}, {}  # user defined
        for case in self.get_cases(case, kwargs):
            color, fruit = case
            benchmark, output = self.conbench.benchmark(
                func,
                self.name,
                tags,
                context,
                github_info,
                kwargs,
            )
            self.conbench.publish(benchmark)
            yield benchmark, output
```

```
$ cd ~/workspace/conbench/conbench/tests/benchmark/
$ conbench subtraction foo.csv

Benchmark result:
{
    "context": {
        "benchmark_language": "Python",
        "benchmark_language_version": "Python 3.9.2"
    },
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/apache/arrow"
    },
    "machine_info": {
        "architecture_name": "x86_64",
        "cpu_core_count": "2",
        "cpu_frequency_max_hz": "3500000000",
        "cpu_l1d_cache_bytes": "32768",
        "cpu_l1i_cache_bytes": "32768",
        "cpu_l2_cache_bytes": "262144",
        "cpu_l3_cache_bytes": "4194304",
        "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
        "cpu_thread_count": "4",
        "kernel_name": "20.5.0",
        "memory_bytes": "17179869184",
        "name": "machine-abc",
        "os_name": "macOS",
        "os_version": "10.16"
    },
    "stats": {
        "batch_id": "eee5880b9d944586a2f24b931b4a770b",
        "data": [
            "0.000007"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000007",
        "mean": "0.000007",
        "median": "0.000007",
        "min": "0.000007",
        "q1": "0.000007",
        "q3": "0.000007",
        "run_id": "eee5880b9d944586a2f24b931b4a770b",
        "stdev": 0,
        "time_unit": "s",
        "times": [],
        "timestamp": "2021-06-21T22:19:07.274226+00:00",
        "unit": "s"
    },
    "tags": {
        "color": "green",
        "count": 1,
        "dataset": "foo.csv",
        "fruit": "apple",
        "name": "subtraction"
    }
}

```
