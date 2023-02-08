<p align="right">
<a href="https://github.com/conbench/conbench/blob/main/.github/workflows/actions.yml"><img alt="Build Status" src="https://github.com/conbench/conbench/actions/workflows/actions.yml/badge.svg?branch=main"></a>
<a href="https://coveralls.io/github/conbench/conbench?branch=main"><img src="https://coveralls.io/repos/github/conbench/conbench/badge.svg?branch=main&kill_cache=06b9891a46827df564072ae831b13897599f7f3d" alt="Coverage Status" /></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

# Conbench

<img src="https://raw.githubusercontent.com/conbench/conbench/main/conbench.png" alt="Language-independent Continuous Benchmarking (CB) Framework">


Conbench allows you to write benchmarks in any language, publish the
results as JSON via an API, and persist them for comparison while
iterating on performance improvements or to guard against regressions.

Conbench includes a runner which can be used as a stand-alone library
for traditional macro benchmark authoring. The runner will time a unit of
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

* [Developer environment](https://github.com/conbench/conbench#developer-environment)
* [Configuring the server](https://github.com/conbench/conbench#configuring-the-server)
* [Creating accounts](https://github.com/conbench/conbench#creating-accounts)
* [Authoring benchmarks](https://github.com/conbench/conbench#authoring-benchmarks)
  * [Simple benchmarks](https://github.com/conbench/conbench#example-simple-benchmarks)
  * [External benchmarks](https://github.com/conbench/conbench#example-external-benchmarks)
  * [Case benchmarks](https://github.com/conbench/conbench#example-case-benchmarks)
  * [R benchmarks](https://github.com/conbench/conbench#example-r-benchmarks)


## Installation

All packages in this repo can be installed from PyPI. Each package uses
[CalVer](https://calver.org/) for versioning. No stability is guaranteed between PyPI
versions, so consider pinning packages to a specific version in your code.

```bash
pip install benchadapt
pip install benchclients
pip install benchconnect
pip install benchrun
pip install conbench  # legacy CLI
```

We typically publish to PyPI often, when new features or bugfixes are needed by users,
but not on every merge to `main`. To install the latest development version, install
from git like so:

```bash
pip install 'benchadapt@git+https://github.com/conbench/conbench.git@main#subdirectory=benchadapt/python'
pip install 'benchclients@git+https://github.com/conbench/conbench.git@main#subdirectory=benchclients/python'
pip install 'benchconnect@git+https://github.com/conbench/conbench.git@main#subdirectory=benchconnect'
pip install 'benchrun@git+https://github.com/conbench/conbench.git@main#subdirectory=benchrun/python'
pip install 'conbench@git+https://github.com/conbench/conbench.git@main'
```


## Developer environment

### Dependencies

- [`make`](https://www.gnu.org/software/make/), [`docker compose`](https://docs.docker.com/compose/install/): common developer tasks depend on these tools. They need to be set up on your system.
- `GITHUB_API_TOKEN` environment variable: set up a GitHub API token using [GitHub's instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token). It's recommended to only give the token read-only permissions to public repositories (which is the default for fine-grained personal access tokens). Run `export GITHUB_API_TOKEN="{token}"` in your current shell.

### Makefile targets

The following Makefile targets implement common developer tasks. They assume to be run in the root folder of the repository.

* `make run-app`: This command lets you experiment with Conbench locally.
It runs the stack in a containerized fashion.
It rebuilds container images from the current checkout, spawns
multiple containers (including one for the database), and then exposes Conbench's
HTTP server on the host at http://127.0.0.1:5000.
The command will stay in the foreground of your terminal, showing log output of all containers.
Once you see access log lines like `GET /api/ping/ HTTP/1.1" 200` you can point your browser to http://127.0.0.1:5000.
You can use `Ctrl+C` to terminate the containerized stack (this only stops containers, and the next invocation of `make run-app` will use previous database state -- invoke `make teardown-app` to stop and remove containers).
If you wish to clear all database tables during local development you can hit http://127.0.0.1:5000/api/wipe-db with the browser or with e.g. curl.

* `make run-app-dev`: Similar to `make run-app`, but also mounts the repository's root directory into the container.
Code changes are (should be) detected automatically and result in automatic code reload.

* `make tests`: The nobrainer command to run the test suite just like CI does.
For more fine-grained control see further below.

* `make lint`: Performs invasive code linting in your local checkout.
May modify files. Analogue to what CI requires.
It requires for some commands to be available in your current shell.
Dependencies can be installed with `pip install -r requirements-dev.txt`.

* `make conbench-on-minikube`: requires [minikube](https://minikube.sigs.k8s.io/docs/start/).
Deploys the Conbench API server to a local minikube-powered Kubernetes cluster.
This also deploys a kube-prometheus-based observability stack.
Use this target for local development in this area.


### View API documentation

Point your browser to http://127.0.0.1:5000/api/docs/.

### Python environment on the host

CI and common developer commands use containerized workflows where dependencies are defined and easy to reason about via `Dockerfile`s.

Note that the CPython version that Conbench is tested with in CI and that it is recommended to be deployed with is currently the latest 3.11.x release, as also defined in `Dockerfile` at the root of this repository.

Some developer tasks may involve running Conbench tooling straight on the host.
Here is how to install the Python dependencies for the Conbench web application:

```bash
pip install -r requirements-webapp.txt
```

Dependencies for running code analysis and tests straight on the host can be installed with

```bash
pip install -r requirements-dev.txt
```

Dependencies for the (legacy) `conbench` CLI can be installed with

```bash
pip install -r requirements-cli.txt
```

### Fine-grained test invocation

If `make test` is too coarse-grained, then this is how to take control of the containerized `pytest` test runner:

```bash
docker compose down && docker compose build app && \
    docker compose run app \
    pytest -vv conbench/tests
```

This command attempts to stop and remove previously spawned test runner containers, and it rebuilds the `app` container image prior to running tests to pick up code changes in the local checkout.

Useful command line arguments for local development (can be combined as desired):

* `... pytest -k test_login`: run only string-matching tests
* `... pytest -x`: exit upon first error
* `... pytest -s`: do not swallow log output during run
* `... run -e CONBENCH_LOG_LEVEL_STDERR=DEBUG app ...`

### Legacy commands

The following commands are not guaranteed to work as documented, but provide valuable inspiration:

#### To autogenerate a migration

    (conbench) $ brew services start postgres
    (conbench) $ dropdb conbench_prod
    (conbench) $ createdb conbench_prod
    (conbench) $ git checkout main && git pull
    (conbench) $ alembic upgrade head
    (conbench) $ git checkout your-branch
    (conbench) $ alembic revision --autogenerate -m "new"


#### To populate local conbench with sample runs and benchmarks

1. Start conbench app in Terminal window 1:

        (conbench) $ dropdb conbench_prod && createdb conbench_prod && alembic upgrade head && flask run

2. Run `conbench.tests.populate_local_conbench` in Terminal window 2 while conbench app is running:

        (conbench) $ python -m conbench.tests.populate_local_conbench


### To upload new version of packages to PyPI

Kick off a new run of the "Build and upload a package to PyPI" workflow on the [Actions
page](https://github.com/conbench/conbench/actions).

## Configuring the web application

The conbench web application can be configured with various environment variables as
defined in [config.py](./conbench/config.py). Instructions are in that file.

## Creating accounts

By default, conbench has open read access, so a user account is not required to
view results or read from the API. An account is required only if the conbench
instance is private or to write data to conbench.

If you do need an account, follow the login screen's "Sign Up" link, and use the
registration key specified in the server configuration above. If you are a user
of conbench, you may need to talk to your user administrator to get the
registration key. SSO can be configured to avoid requiring the registration key.

If you have an account and need to create an additional account (say for a machine
user of the API) either repeat the process if you have the registration key, or if
you don't have the registration key (say if your account uses SSO), when logged in,
go to the gear menu / Users and use the "Add User" button to create a new account
without the registration key.

## Authoring benchmarks

There are three main types of benchmarks: "simple benchmarks" that time the
execution of a unit of work, "external benchmarks" that just record benchmark
results that were obtained from some other benchmarking tool, and "case
benchmarks" which benchmark a unit of work under different scenarios (cases).

Included in this repository are contrived, minimal examples of these different
kinds of benchmarks to be used as templates for benchmark authoring. These
example benchmarks and their tests can be found here:


* [_example_benchmarks.py](https://github.com/conbench/conbench/blob/main/conbench/tests/benchmark/_example_benchmarks.py)
* [test_cli.py](https://github.com/conbench/conbench/blob/main/conbench/tests/benchmark/test_cli.py)
* [test_runner.py](https://github.com/conbench/conbench/blob/main/conbench/tests/benchmark/test_runner.py)


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
    name = "addition"

    def run(self, **kwargs):
        yield self.conbench.benchmark(
            self._get_benchmark_function(), self.name, options=kwargs
        )

    def _get_benchmark_function(self):
        return lambda: 1 + 1
```

Successfully registered benchmarks appear in the `conbench --help` list.
For this benchmark to appear, the file must match the following paterns (documented in the [`utils.py:register_benchmarks` function](https://github.com/conbench/conbench/blob/35fde9954e2b365e36472f16b46fe3067e9dc455/conbench/util.py#L104):
* `benchmark*.py`
* `*benchmark.py`
* `*benchmarks.py`

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
  --run-name TEXT        Free-text name of run (commit ABC, pull request 123,
                         etc).
  --run-reason TEXT      Low-cardinality reason for run (commit, pull request,
                         manual, etc).
  --help                 Show this message and exit.
```

Example command line execution:

```
(conbench) $ cd ~/workspace/conbench/conbench/tests/benchmark/
(conbench) $ conbench addition

Benchmark result:
{
    "batch_id": "c9db942c27db4359923eb08aa553beb7",
    "run_id": "f6c7d0b3b3f146f9b1ad297fc6e5776b",
    "timestamp": "2021-11-09T22:09:17.790397+00:00",
    "context": {
        "benchmark_language": "Python"
    },
    "github": {
        "commit": "61dec915b9dd230ca5029f5e586f8bd95c3e0c05",
        "repository": "https://github.com/conbench/conbench"
    },
    "info": {
        "benchmark_language_version": "Python 3.9.7"
    },
    "machine_info": {
        "architecture_name": "arm64",
        "cpu_core_count": "8",
        "cpu_frequency_max_hz": "0",
        "cpu_l1d_cache_bytes": "65536",
        "cpu_l1i_cache_bytes": "131072",
        "cpu_l2_cache_bytes": "4194304",
        "cpu_l3_cache_bytes": "0",
        "cpu_model_name": "Apple M1",
        "cpu_thread_count": "8",
        "gpu_count": "0",
        "gpu_product_names": [],
        "kernel_name": "20.6.0",
        "memory_bytes": "17179869184",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "11.5.2"
    },
    "stats": {
        "data": [
            "0.000001"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000001",
        "mean": "0.000001",
        "median": "0.000001",
        "min": "0.000001",
        "q1": "0.000001",
        "q3": "0.000001",
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
  "run_id": "dfe3a816ca9e451a9da7d940a974cb95",
  "batch_id": "0e869934b391424a8199c485dfbbc066",
  "timestamp": "2021-11-09T22:11:25.262330+00:00",
  "stats": {
    "data": [
      "0.000002",
      "0.000001",
      "0.000000",
      "0.000001",
      "0.000001",
      "0.000001",
      "0.000001",
      "0.000000",
      "0.000001",
      "0.000001"
    ],
    "times": [],
    "unit": "s",
    "time_unit": "s",
    "iterations": 10,
    "mean": "0.000001",
    "median": "0.000001",
    "min": "0.000000",
    "max": "0.000002",
    "stdev": "0.000001",
    "q1": "0.000001",
    "q3": "0.000001",
    "iqr": "0.000000"
  },
  "machine_info": {
    "name": "diana",
    "os_name": "macOS",
    "os_version": "11.5.2",
    "architecture_name": "arm64",
    "kernel_name": "20.6.0",
    "memory_bytes": "17179869184",
    "cpu_model_name": "Apple M1",
    "cpu_core_count": "8",
    "cpu_thread_count": "8",
    "cpu_l1d_cache_bytes": "65536",
    "cpu_l1i_cache_bytes": "131072",
    "cpu_l2_cache_bytes": "4194304",
    "cpu_l3_cache_bytes": "0",
    "cpu_frequency_max_hz": "0",
    "gpu_count": "0",
    "gpu_product_names": []
  },
  "context": {
    "benchmark_language": "Python"
  },
  "info": {
    "benchmark_language_version": "Python 3.9.7"
  },
  "tags": {
    "name": "addition"
  },
  "github": {
    "commit": "61dec915b9dd230ca5029f5e586f8bd95c3e0c05",
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
  --run-name TEXT        Free-text name of run (commit ABC, pull request 123,
                         etc).
  --run-reason TEXT      Low-cardinality reason for run (commit, pull request,
                         manual, etc).
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
    "info": {},
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

### Example simple benchmarks executed on machine cluster instead of one machine

If your benchmark is executed on a machine cluster instead of one machine, you
can capture cluster info in the following manner.
Note that a benchmark will have a continuous history on a specific cluster as long as cluster's `name` and `info` do not change.
There is also an `optional_info` field for information that should not impact the cluster's hash (and thus disrupt the distribution history), but should still be recorded.
```python
import conbench.runner


@conbench.runner.register_benchmark
class SimpleBenchmarkWithClusterInfo(conbench.runner.Benchmark):
    name = "product"

    def run(self, **kwargs):
        cluster_info = {
            "name": "cluster 1",
            "info": {"gpu": 1},
            "optional_info": {"workers": 2},
        }
        yield self.conbench.benchmark(
            self._get_benchmark_function(),
            self.name,
            cluster_info=cluster_info,
            options=kwargs,
        )

    def _get_benchmark_function(self):
        return lambda: 1 * 2
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
  --run-name TEXT        Free-text name of run (commit ABC, pull request 123,
                         etc).
  --run-reason TEXT      Low-cardinality reason for run (commit, pull request,
                         manual, etc).
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
    "batch_id": "13b87cc6d9a84f2188df279d8c513933",
    "run_id": "48acd853b8294df9a1f5457f192456f3",
    "timestamp": "2021-11-09T22:15:23.501923+00:00",
    "context": {
        "benchmark_language": "Python"
    },
    "github": {
        "commit": "61dec915b9dd230ca5029f5e586f8bd95c3e0c05",
        "repository": "https://github.com/conbench/conbench"
    },
    "info": {
        "benchmark_language_version": "Python 3.9.7"
    },
    "machine_info": {
        "architecture_name": "arm64",
        "cpu_core_count": "8",
        "cpu_frequency_max_hz": "0",
        "cpu_l1d_cache_bytes": "65536",
        "cpu_l1i_cache_bytes": "131072",
        "cpu_l2_cache_bytes": "4194304",
        "cpu_l3_cache_bytes": "0",
        "cpu_model_name": "Apple M1",
        "cpu_thread_count": "8",
        "gpu_count": "0",
        "gpu_product_names": [],
        "kernel_name": "20.6.0",
        "memory_bytes": "17179869184",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "11.5.2"
    },
    "run_id": "48acd853b8294df9a1f5457f192456f3",
    "stats": {
        "data": [
            "0.000004"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000004",
        "mean": "0.000004",
        "median": "0.000004",
        "min": "0.000004",
        "q1": "0.000004",
        "q3": "0.000004",
        "stdev": 0,
        "time_unit": "s",
        "times": [],
        "unit": "s"
    },
    "tags": {
        "columns": "10",
        "name": "matrix",
        "rows": "10"
    },
    "timestamp": "2021-11-09T22:15:23.397819+00:00"
}

Benchmark result:
{
    "batch_id": "13b87cc6d9a84f2188df279d8c513933",
    "context": {
        "benchmark_language": "Python"
    },
    "github": {
        "commit": "61dec915b9dd230ca5029f5e586f8bd95c3e0c05",
        "repository": "https://github.com/conbench/conbench"
    },
    "info": {
        "benchmark_language_version": "Python 3.9.7"
    },
    "machine_info": {
        "architecture_name": "arm64",
        "cpu_core_count": "8",
        "cpu_frequency_max_hz": "0",
        "cpu_l1d_cache_bytes": "65536",
        "cpu_l1i_cache_bytes": "131072",
        "cpu_l2_cache_bytes": "4194304",
        "cpu_l3_cache_bytes": "0",
        "cpu_model_name": "Apple M1",
        "cpu_thread_count": "8",
        "gpu_count": "0",
        "gpu_product_names": [],
        "kernel_name": "20.6.0",
        "memory_bytes": "17179869184",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "11.5.2"
    },
    "stats": {
        "data": [
            "0.000004"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000004",
        "mean": "0.000004",
        "median": "0.000004",
        "min": "0.000004",
        "q1": "0.000004",
        "q3": "0.000004",
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
    "batch_id": "13b87cc6d9a84f2188df279d8c513933",
    "run_id": "48acd853b8294df9a1f5457f192456f3",
    "timestamp": "2021-11-09T22:15:23.509211+00:00",
    "context": {
        "benchmark_language": "Python"
    },
    "github": {
        "commit": "61dec915b9dd230ca5029f5e586f8bd95c3e0c05",
        "repository": "https://github.com/conbench/conbench"
    },
    "info": {
        "benchmark_language_version": "Python 3.9.7"
    },
    "machine_info": {
        "architecture_name": "arm64",
        "cpu_core_count": "8",
        "cpu_frequency_max_hz": "0",
        "cpu_l1d_cache_bytes": "65536",
        "cpu_l1i_cache_bytes": "131072",
        "cpu_l2_cache_bytes": "4194304",
        "cpu_l3_cache_bytes": "0",
        "cpu_model_name": "Apple M1",
        "cpu_thread_count": "8",
        "gpu_count": "0",
        "gpu_product_names": [],
        "kernel_name": "20.6.0",
        "memory_bytes": "17179869184",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "11.5.2"
    },
    "stats": {
        "data": [
            "0.000002"
        ],
        "iqr": "0.000000",
        "iterations": 1,
        "max": "0.000002",
        "mean": "0.000002",
        "median": "0.000002",
        "min": "0.000002",
        "q1": "0.000002",
        "q3": "0.000002",
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
        info, context = self.conbench.get_r_info_and_context()

        yield self.conbench.record(
            {"data": [result], "unit": "s"},
            self.name,
            info=info,
            context=context,
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
            "start_time <- Sys.time();"
            "addition(); "
            "end_time <- Sys.time(); "
            "result <- end_time - start_time; "
            "as.numeric(result); "
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
  --run-name TEXT        Free-text name of run (commit ABC, pull request 123,
                         etc).
  --run-reason TEXT      Low-cardinality reason for run (commit, pull request,
                         manual, etc).
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
        info, context = self.conbench.get_r_info_and_context()

        for _ in range(iterations):
            if kwargs.get("drop_caches", False):
                self.conbench.sync_and_drop_caches()
            result, output = self._run_r_command()
            data.append(result["result"][0]["real"])

        yield self.conbench.record(
            {"data": data, "unit": "s"},
            self.name,
            info=info,
            context=context,
            options=kwargs,
            output=output,
        )

    def _run_r_command(self):
        r_command = self._get_r_command()
        self.conbench.execute_r_command(r_command)
        with open("placebo.json") as json_file:
            data = json.load(json_file)
        return data, json.dumps(data, indent=2)

    def _get_r_command(self):
        return (
            "library(arrowbench); "
            "out <- run_one(arrowbench:::placebo); "
            "cat(jsonlite::toJSON(out), file='placebo.json'); "
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
  --run-name TEXT        Free-text name of run (commit ABC, pull request 123,
                         etc).
  --run-reason TEXT      Low-cardinality reason for run (commit, pull request,
                         manual, etc).
  --help                 Show this message and exit.
```
