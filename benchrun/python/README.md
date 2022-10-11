# Python {benchrun}

{benchrun} is a Python package to run macrobenchmarks, deliberately designed to work
well with the larger conbench ecosystem.

## Installation

{benchrun} is not [yet] on a package archive like PyPI; you can install from GitHub
with

```shell
pip install benchrun@git+https://github.com/conbench/conbench.git@main#subdirectory=benchrun/python
```

## Writing benchmarks

### `Iteration`

The code to run for a benchmark is contained in a class inheriting from the abstract
`Iteration` class. At a minimum, users must override the `name` attribute and `run()`
method (the code to time), but may also override `setup()`, `before_each()`,
`after_each()` and `teardown()` methods, where `*_each()` runs before/after each
iteration, and `setup()` and `teardown()` run once before/after all iterations. A
simple implementation might look like

```python
import time

from benchrun import Iteration

class MyIteration(Iteration):
    name = "my-iteration"

    def before_each(self, case: dict) -> None:
        # use the `env` dict attribute to pass data between stages
        self.env = {"success": False}

    def run(self, case: dict) -> dict:
        # code to time goes here
        time.sleep(case["sleep_seconds"])
        self.env["success"] = True

    def after_each(self, case: dict) -> None:
        assert run_results["success"]
        self.env = {}
```

### `CaseList`

An `Iteration`'s methods are parameterized with `case`, a dict where keys are
parameters for the benchmark, and the values are scalar arguments. Cases are managed
with an instance of `CaseList`, a class which takes a `params` dict, which is like a
case dict with the difference that the arguments are lists of valid arguments, not
scalars. `CaseList` will populate a `case_list` attribute which contains the grid of
specified cases to be run:

```python
from benchrun import CaseList

case_list = CaseList(params={"x": [1, 2], "y": ["a", "b", "c"]})
case_list.case_list
#> [{'x': 1, 'y': 'a'},
#>  {'x': 1, 'y': 'b'},
#>  {'x': 1, 'y': 'c'},
#>  {'x': 2, 'y': 'a'},
#>  {'x': 2, 'y': 'b'},
#>  {'x': 2, 'y': 'c'}]
```

`CaseList` contains an overridable `filter_cases()` method that can be used to remove
invalid combinations of parameters, e.g. if an `x` of `2` with a `y` of `b` is not
viable:

```python
class MyCaseList(CaseList):
    def filter_cases(self, case_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered_case_list = []
        for case in case_list:
            if not (case["x"] == 2 and case["y"] == "b"):
                filtered_case_list.append(case)

        return filtered_case_list

my_case_list = MyCaseList(params={"x": [1, 2], "y": ["a", "b", "c"]})
my_case_list.case_list
#> [{'x': 1, 'y': 'a'},
#>  {'x': 1, 'y': 'b'},
#>  {'x': 1, 'y': 'c'},
#>  {'x': 2, 'y': 'a'},
#>  {'x': 2, 'y': 'c'}]
```

If there are so many restrictions that it is simpler to specify which cases are
viable than which are not, the `case_list` parameter of `filter_cases()` can be
completely ignored and a manually-generated list can be returned.

### `Benchmark`

A `Benchmark` in {benchrun} consists of an `Iteration` instance, a `CaseList`
instance, and potentially a bit more metadata about how to run it like whether to
drop disk caches beforehand.

```python
my_benchmark = Benchmark(iteration=my_iteration, case_list=my_case_list)
```

This class has a `run()` method to run all cases, or `run_case()` to run a single
case.

### `BenchmarkList`

A `BenchmarkList` is a lightweight class to tie together all the instances of
`Benchmark` that should be run together (e.g. all the benchmarks for a package).

```python
from benchrun import BenchmarkList

my_benchmark_list = BenchmarkList(benchmarks = [my_benchmark])
```

The class has a `__call__()` method that will run all benchmarks in its list,
taking care that they all use the same `run_id` so they will all appear together
on conbench.

## Running benchmarks and sending results to conbench

`BenchmarkList` is designed to work seamlessly with
{[benchadapt](https://github.com/conbench/conbench/tree/main/benchadapt/python)}'s
`CallableAdapter` class:

```python
from benchadapt.adapters import CallableAdapter

my_adapter = CallableAdapter(callable=my_benchmark_list)
```

Like all adapters, it then has a `run()` method to run all the benchmarks it
contains (handling generic metadata appropriately for you), a `post_results()`
method that will send the results to a conbench server, and a `__call__()` method
that will do both. These are the methods that should be called in whatever CI or
automated build system will be used for running benchmarks.

## Setting more metadata

{benchrun} and {benchadapt} make an effort to handle as much metadata for you as
possible (e.g. things like machine info), but you will still need to specify some
metadata yourself, e.g. build flags used in compilation or things like `run_reason`
(often something like `commit` or `merge`). To see what actually gets sent to
conbench, see the documentation for `benchadapt.BenchmarkResult`.
