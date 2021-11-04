<p align="right">
<a href="https://github.com/conbench/conbench/blob/main/.github/workflows/actions.yml"><img alt="Build Status" src="https://github.com/conbench/conbench/actions/workflows/actions.yml/badge.svg?branch=main"></a>
<a href="https://coveralls.io/github/conbench/conbench?branch=main"><img src="https://coveralls.io/repos/github/conbench/conbench/badge.svg?branch=main&kill_cache=06b9891a46827df564072ae831b13897599f7f3d" alt="Coverage Status" /></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

# Conbench


<img src="https://github.com/conbench/conbench/blob/main/conbench.png" alt="Language-independent Continuous Benchmarking (CB) Framework">


Conbench allows you to write benchmarks in any language, publish the
results as JSON via an API, and persist them for comparison while
iterating on performance improvements or to guard against regressions.

Conbench includes a runner which can be used as a stand-alone library
for traditional benchmark authoring. The runner will time a unit of
work (or measure throughput), collect machine information that may be relevant
for hardware specific optimizations, and return JSON formatted results.

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
execute their external C++/R/Java/JavaScript benchmarks and record those results
too. Those benchmarks can be found in the
[ursacomputing/benchmarks](https://github.com/ursacomputing/benchmarks)
repository, and the results are hosted on the
[Arrow Conbench Server](https://conbench.ursa.dev/).


- May 2021: https://ursalabs.org/blog/announcing-conbench/


<br>


## Index

* [Contributing](https://github.com/conbench/conbench#contributing)
* [Authoring benchmarks](https://github.com/conbench/conbench#authoring-benchmarks)
  * [Simple benchmarks](https://github.com/conbench/conbench#example-simple-benchmarks)
  * [External benchmarks](https://github.com/conbench/conbench#example-external-benchmarks)
  * [Case benchmarks](https://github.com/conbench/conbench#example-case-benchmarks)
  * [R benchmarks](https://github.com/conbench/conbench#example-r-benchmarks)


## Contributing


### Create workspace
    $ cd
    $ mkdir -p envs
    $ mkdir -p workspace


### Create virualenv
    $ cd ~/envs
    $ python3 -m venv conbench
    $ source conbench/bin/activate


### Clone repository
    (conbench) $ cd ~/workspace/
    (conbench) $ git clone https://github.com/conbench/conbench.git


### Install dependencies
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ pip install -r requirements-test.txt
    (conbench) $ pip install -r requirements-build.txt
    (conbench) $ pip install -r requirements-cli.txt
    (conbench) $ pip install -e .


### Start postgres

Mac

    $ brew services start postgres

Linux

    $ sudo service postgresql start


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

If you get an authentication error, set the password for your user.

    $ psql
    # ALTER USER <username> PASSWORD '<password>';

Then, set an environmental variable `DB_PASSWORD` to reflect the chosen password.

    $ export DB_PASSWORD=<password>

Alternatively, if you don't want to set the `DB_PASSWORD` you can change the
password in postgres to `postgres`.

    $ psql
    # ALTER USER <username> PASSWORD 'postgres';


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


### Format code
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ black .
        reformatted foo.py
    (conbench) $ git add foo.py


### Sort imports
    (conbench) $ cd ~/workspace/conbench/
    (conbench) $ isort .
        Fixing foo.py
    (conbench) $ git add foo.py


### Lint code
    (qa) $ cd ~/workspace/conbench/
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


### To upload new version of conbench package to PyPI
1. Update version in [setup.py](setup.py)
2. Commit your change into `main` branch

New version of conbench package will be uploaded into PyPI by a new build for [conbench-deploy](.buildkite/conbench-deploy/pipeline.yml) Buildkite pipeline

## Authoring benchmarks

There are three main types of benchmarks: "simple benchmarks" that time the
execution of a unit of work, "external benchmarks" that just record benchmark
results that were obtained from some other benchmarking tool, and "case
benchmarks" which benchmark a unit of work under different scenarios (cases).

Included in this repository are contrived, minimal examples of these different
kinds of benchmarks to be used as templates for benchmark authoring. These
example benchmarks and their tests can be found here:


* [_example_benchmarks.py](https://github.com/conbench/conbench/blob/main/conbench/tests/benchmark/_example_benchmarks.py)
* [test_cli.py](https://github.com/conbench/conbench/blob/main/conbench/tests/benchmark/test_runner.py)
* [test_runner.py](https://github.com/conbench/conbench/blob/main/conbench/tests/benchmark/test_cli.py)


### Example simple benchmarks

A "simple benchmark" runs and records the execution time of a unit of work.

Implementation details: Note that this benchmark extends
`conbench.runner.Benchmark`, implements the minimum required `run()`
method, and registers itself with the `@conbench.runner.register_benchmark`
decorator.

```python
import conbench.runner


@conbench.runner.register_benchmark
class SimpleBenchmark(conbench.runner.Benchmark):
    """Example simple benchmark."""

    name = "addition"

    def run(self, **kwargs):
        yield self.conbench.benchmark(
            self._get_benchmark_function(), self.name, options=kwargs
        )

    def _get_benchmark_function(self):
        return lambda: 1 + 1
```

Successfully registered benchmarks appear in the `conbench --help` list.

```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench --help
Usage: conbench [OPTIONS] COMMAND [ARGS]...

  Conbench: Language-independent Continuous Benchmarking (CB) Framework

Options:
  --help  Show this message and exit.

Commands:
  addition            Run addition benchmark.
  external            Run external benchmark.
  external-r          Run external-r benchmark.
  external-r-options  Run external-r-options benchmark.
  list                List of benchmarks (for orchestration).
  matrix              Run matrix benchmark(s).
  version             Display Conbench version.
```

Benchmarks can be run from command line within the directory where the
benchmarks are defined.

Benchmark classes can also be imported and executed via the `run` method which
accepts the same arguments that appear in the command line help.

```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench addition --help

Usage: conbench addition [OPTIONS]

  Run addition benchmark.

Options:
  --iterations INTEGER   [default: 1]
  --drop-caches BOOLEAN  [default: false]
  --gc-collect BOOLEAN   [default: true]
  --gc-disable BOOLEAN   [default: true]
  --show-result BOOLEAN  [default: true]
  --show-output BOOLEAN  [default: false]
  --run-id TEXT          Group executions together with a run id.
  --run-name TEXT        Name of run (commit, pull request, etc).
  --help                 Show this message and exit.
```

Example command line execution:

```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench addition

Benchmark result:
{
    "run_id": "c7e5280e65d24ec19d64a7636cef1bd4",
    "batch_id": "c7e5280e65d24ec19d64a7636cef1bd4",
    "timestamp": "2021-06-21T22:18:16.752993+00:00",
    "context": {
        "benchmark_language": "Python",
        "benchmark_language_version": "Python 3.9.2"
    },
    "github": {
        "commit": "58fb35dc593dca82c917cf18c1c65c059b9fb12c",
        "repository": "https://github.com/conbench/conbench"
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
        "stdev": 0,
        "time_unit": "s",
        "times": [],
        "unit": "s"
    },
    "tags": {
        "name": "addition"
    }
}
```

Example Python execution:

```
(conbench) $ python
>>> import json
>>> from conbench.tests.benchmark import _example_benchmarks
>>> benchmark = _example_benchmarks.SimpleBenchmark()
>>> [(result, output)] = benchmark.run(iterations=10)
>>> output
2
>>> print(json.dumps(result, indent=2))
{
  "run_id": "9dc1beadf4bb46e0ac86cd0bb6fe201f",
  "batch_id": "9dc1beadf4bb46e0ac86cd0bb6fe201f",
  "timestamp": "2021-08-20T16:05:57.299148+00:00",
  "stats": {
    "data": [
      "0.000004",
      "0.000000",
      "0.000001",
      "0.000000",
      "0.000000",
      "0.000001",
      "0.000000",
      "0.000001",
      "0.000000",
      "0.000000"
    ],
    "times": [],
    "unit": "s",
    "time_unit": "s",
    "iterations": 10,
    "mean": "0.000001",
    "median": "0.000000",
    "min": "0.000000",
    "max": "0.000004",
    "stdev": "0.000001",
    "q1": "0.000000",
    "q3": "0.000001",
    "iqr": "0.000001"
  },
  "machine_info": {
    "name": "machine-xyz",
    "os_name": "macOS",
    "os_version": "10.16",
    "architecture_name": "x86_64",
    "kernel_name": "20.5.0",
    "memory_bytes": "17179869184",
    "cpu_model_name": "Apple M1",
    "cpu_core_count": "8",
    "cpu_thread_count": "8",
    "cpu_l1d_cache_bytes": "65536",
    "cpu_l1i_cache_bytes": "131072",
    "cpu_l2_cache_bytes": "4194304",
    "cpu_l3_cache_bytes": "0",
    "cpu_frequency_max_hz": "2400000000"
  },
  "context": {
    "benchmark_language": "Python",
    "benchmark_language_version": "Python 3.9.6"
  },
  "tags": {
    "name": "addition"
  },
  "github": {
    "commit": "58fb35dc593dca82c917cf18c1c65c059b9fb12c",
    "repository": "https://github.com/conbench/conbench"
  }
}
```

By default, Conbench will try to publish your results to a Conbench server. If
you don't have one running or are missing a `.conbench` credentials file, you'll
see error messages like the following when you execute benchmarks.

```
POST http://localhost:5000/api/login/ failed
{
  "code": 400,
  "description": {
    "_errors": [
      "Invalid email or password."
    ]
  },
  "name": "Bad Request"
}

POST http://localhost:5000/api/benchmarks/ failed
{
  "code": 401,
  "name": "Unauthorized"
}
```

To publish your results to a Conbench server, place a `.conbench` file in the
same directory as your benchmarks. The `cat` command below shows the contents
of an example `.conbench` config file.

```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ cat .conbench
url: http://localhost:5000
email: you@example.com
password: conbench
```

If you don't yet have a Conbench server user account, you'll need to create one
to publish results (registration key defaults to `conbench`).

- http://localhost:5000/register/


### Example external benchmarks

An "external benchmark" records results that were obtained from some other
benchmarking tool (like executing an R benchmark from command line, parsing
the resulting JSON, and recording those results).

Implementation details: Note that the following benchmark sets
`external = True`, and calls `self.conbench.record()` rather than
`self.conbench.benchmark()` as the example above does.

```python
import conbench.runner


@conbench.runner.register_benchmark
class ExternalBenchmark(conbench.runner.Benchmark):
    """Example benchmark that just records external results."""

    external = True
    name = "external"

    def run(self, **kwargs):
        # external results from an API call, command line execution, etc
        result = {
            "data": [100, 200, 300],
            "unit": "i/s",
            "times": [0.100, 0.200, 0.300],
            "time_unit": "s",
        }

        context = {"benchmark_language": "C++"}
        yield self.conbench.record(
            result, self.name, context=context, options=kwargs, output=result
        )
```


```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench external --help

Usage: conbench external [OPTIONS]

  Run external benchmark.

Options:
  --show-result BOOLEAN  [default: true]
  --show-output BOOLEAN  [default: false]
  --run-id TEXT          Group executions together with a run id.
  --run-name TEXT        Name of run (commit, pull request, etc).
  --help                 Show this message and exit.
```


Note that the use of `--iterations=3` results in 3 runs of the benchmark, and
the `mean`, `stdev`, etc calculated.


```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench external --iterations=3

Benchmark result:
{
    "run_id": "8058dde1491b49e5bd514646797c2a20",
    "batch_id": "8058dde1491b49e5bd514646797c2a20",
    "timestamp": "2021-06-21T22:16:54.786499+00:00",
    "context": {
        "benchmark_language": "C++"
    },
    "github": {
        "commit": "58fb35dc593dca82c917cf18c1c65c059b9fb12c",
        "repository": "https://github.com/conbench/conbench"
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
        "stdev": "100.000000",
        "time_unit": "s",
        "times": [
            "0.100000",
            "0.200000",
            "0.300000"
        ],
        "unit": "i/s"
    },
    "tags": {
        "name": "external"
    }
}
```

### Example case benchmarks

A "case benchmark" is a either a "simple benchmark" or an "external benchmark"
executed under various predefined scenarios (cases).

Implementation details: Note that the following benchmark declares the valid
combinations in `valid_cases`, which reads like a CSV (the first row contains
the cases names).


```python
import conbench.runner


@conbench.runner.register_benchmark
class CasesBenchmark(conbench.runner.Benchmark):
    """Example benchmark with cases."""

    name = "matrix"
    valid_cases = (
        ("rows", "columns"),
        ("10", "10"),
        ("2", "10"),
        ("10", "2"),
    )

    def run(self, case=None, **kwargs):
        for case in self.get_cases(case, kwargs):
            rows, columns = case
            tags = {"rows": rows, "columns": columns}
            func = self._get_benchmark_function(rows, columns)
            benchmark, output = self.conbench.benchmark(
                func,
                self.name,
                tags=tags,
                options=kwargs,
            )
            yield benchmark, output

    def _get_benchmark_function(self, rows, columns):
        return lambda: int(rows) * [int(columns) * [0]]
```


```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench matrix --help

Usage: conbench matrix [OPTIONS]

  Run matrix benchmark(s).

  For each benchmark option, the first option value is the default.

  Valid benchmark combinations:
  --rows=10 --columns=10
  --rows=2 --columns=10
  --rows=10 --columns=2

  To run all combinations:
  $ conbench matrix --all=true

Options:
  --rows [10|2]
  --columns [10|2]
  --all BOOLEAN          [default: false]
  --iterations INTEGER   [default: 1]
  --drop-caches BOOLEAN  [default: false]
  --gc-collect BOOLEAN   [default: true]
  --gc-disable BOOLEAN   [default: true]
  --show-result BOOLEAN  [default: true]
  --show-output BOOLEAN  [default: false]
  --run-id TEXT          Group executions together with a run id.
  --run-name TEXT        Name of run (commit, pull request, etc).
  --help                 Show this message and exit.
    """
```


Note that the use of `--all=true` results in 3 benchmark results, one for each
case (`10 x 10`, `2, x 10`, and `10, x 2`).


```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench matrix --all=true

Benchmark result:
{
    "run_id": "d509f6e80ed440a09af60fe1847dc033",
    "batch_id": "d509f6e80ed440a09af60fe1847dc033",
    "timestamp": "2021-06-22T18:39:53.805714+00:00",
    "context": {
        "benchmark_language": "Python",
        "benchmark_language_version": "Python 3.9.2"
    },
    "github": {
        "commit": "58fb35dc593dca82c917cf18c1c65c059b9fb12c",
        "repository": "https://github.com/conbench/conbench"
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
        "data": [
            "0.000010"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000010",
        "mean": "0.000010",
        "median": "0.000010",
        "min": "0.000010",
        "q1": "0.000010",
        "q3": "0.000010",
        "stdev": 0,
        "time_unit": "s",
        "times": [],
        "unit": "s"
    },
    "tags": {
        "columns": "10",
        "name": "matrix",
        "rows": "10"
    }
}

Benchmark result:
{
    "run_id": "d509f6e80ed440a09af60fe1847dc033",
    "batch_id": "d509f6e80ed440a09af60fe1847dc033",
    "timestamp": "2021-06-22T18:39:53.830928+00:00",
    "context": {
        "benchmark_language": "Python",
        "benchmark_language_version": "Python 3.9.2"
    },
    "github": {
        "commit": "58fb35dc593dca82c917cf18c1c65c059b9fb12c",
        "repository": "https://github.com/conbench/conbench"
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
        "data": [
            "0.000006"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000006",
        "mean": "0.000006",
        "median": "0.000006",
        "min": "0.000006",
        "q1": "0.000006",
        "q3": "0.000006",
        "stdev": 0,
        "time_unit": "s",
        "times": [],
        "unit": "s"
    },
    "tags": {
        "columns": "10",
        "name": "matrix",
        "rows": "2"
    }
}

Benchmark result:
{
    "run_id": "d509f6e80ed440a09af60fe1847dc033",
    "batch_id": "d509f6e80ed440a09af60fe1847dc033",
    "timestamp": "2021-06-22T18:39:53.843815+00:00",
    "context": {
        "benchmark_language": "Python",
        "benchmark_language_version": "Python 3.9.2"
    },
    "github": {
        "commit": "58fb35dc593dca82c917cf18c1c65c059b9fb12c",
        "repository": "https://github.com/conbench/conbench"
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
        "stdev": 0,
        "time_unit": "s",
        "times": [],
        "unit": "s"
    },
    "tags": {
        "columns": "2",
        "name": "matrix",
        "rows": "10"
    }
}
```

### Example R benchmarks

Here are a few examples illustrating how to integrate R benchmarks with
Conbench.

The first one just times `1 + 1` in R, and the second one executes an R
benchmark from a library of R benchmarks (in this case
[arrowbench](https://github.com/ursacomputing/arrowbench)).

If you find yourself wrapping a lot of R benchmarks in Python to integrate them
with Conbench (to get uniform JSON benchmark results which you can persist and
publish on a Conbench server), you'll probably want to extract much of the
boilerplate out into a base class.


```python
import conbench.runner


@conbench.runner.register_benchmark
class ExternalBenchmarkR(conbench.runner.Benchmark):
    """Example benchmark that records an R benchmark result."""

    external = True
    name = "external-r"

    def run(self, **kwargs):
        result, output = self._run_r_command()
        yield self.conbench.record(
            {"data": [result], "unit": "s"},
            self.name,
            context=self.conbench.r_info,
            options=kwargs,
            output=output,
        )

    def _run_r_command(self):
        output, _ = self.conbench.execute_r_command(self._get_r_command())
        result = float(output.split("\n")[-1].split("[1] ")[1])
        return result, output

    def _get_r_command(self):
        return (
            f"addition <- function() { 1 + 1 }; "
            f"start_time <- Sys.time();"
            f"addition(); "
            f"end_time <- Sys.time(); "
            f"result <- end_time - start_time; "
            f"as.numeric(result); "
        )
```


```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench external-r --help

Usage: conbench external-r [OPTIONS]

  Run external-r benchmark.

Options:
  --show-result BOOLEAN  [default: true]
  --show-output BOOLEAN  [default: false]
  --run-id TEXT          Group executions together with a run id.
  --run-name TEXT        Name of run (commit, pull request, etc).
  --help                 Show this message and exit.
```


```python
import json

import conbench.runner


@conbench.runner.register_benchmark
class ExternalBenchmarkOptionsR(conbench.runner.Benchmark):
    """Example benchmark that records an R benchmark result (with options)."""

    external = True
    name = "external-r-options"
    options = {
        "iterations": {"default": 1, "type": int},
        "drop_caches": {"type": bool, "default": "false"},
    }

    def run(self, **kwargs):
        data, iterations = [], kwargs.get("iterations", 1)

        for _ in range(iterations):
            if kwargs.get("drop_caches", False):
                self.conbench.sync_and_drop_caches()
            result, output = self._run_r_command()
            data.append(result["result"][0]["real"])

        yield self.conbench.record(
            {"data": data, "unit": "s"},
            self.name,
            context=self.conbench.r_info,
            options=kwargs,
            output=output,
        )

    def _run_r_command(self):
        r_command = self._get_r_command()
        self.conbench.execute_r_command(r_command)
        with open('placebo.json') as json_file:
            data = json.load(json_file)
        return data, json.dumps(data, indent=2)

    def _get_r_command(self):
        return (
            f"library(arrowbench); "
            f"out <- run_one(arrowbench:::placebo); "
            f"cat(jsonlite::toJSON(out), file='placebo.json'); "
        )
```

```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench external-r --help

Usage: conbench external-r-options [OPTIONS]

  Run external-r-options benchmark.

Options:
  --iterations INTEGER   [default: 1]
  --drop-caches BOOLEAN  [default: false]
  --show-result BOOLEAN  [default: true]
  --show-output BOOLEAN  [default: false]
  --run-id TEXT          Group executions together with a run id.
  --run-name TEXT        Name of run (commit, pull request, etc).
  --help                 Show this message and exit.
```
