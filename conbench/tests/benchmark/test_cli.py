import unittest.mock
import os

from ...util import register_benchmarks


CONBENCH = """
Usage: conbench [OPTIONS] COMMAND [ARGS]...

  Conbench: Language-independent Continuous Benchmarking (CB) Framework

Options:
  --help  Show this message and exit.

Commands:
  addition  Run addition benchmark.
  external  Run external benchmark.
  list      List of benchmarks (for orchestration).
  matrix    Run matrix benchmark(s).
"""

CONBENCH_LIST = """
[
  {
    "command": "addition --iterations=2"
  },
  {
    "command": "external --iterations=2"
  },
  {
    "command": "matrix --all=true --iterations=2"
  }
]
"""


CONBENCH_ADDITION = """
Benchmark output:
2
"""


CONBENCH_ADDITION_HELP = """
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


CONBENCH_MATRIX = """
Benchmark output:
[[0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]
"""


CONBENCH_MATRIX_HELP = """
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
  --all BOOLEAN          [default: False]
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


CONBENCH_EXTERNAL = """
Benchmark output:
{'data': [100, 200, 300], 'unit': 'i/s', 'times': [0.1, 0.2, 0.3], 'time_unit': 's'}
"""


CONBENCH_EXTERNAL_HELP = """
Usage: conbench external [OPTIONS]

  Run external benchmark.

Options:
  --show-result BOOLEAN  [default: True]
  --show-output BOOLEAN  [default: False]
  --run-id TEXT          Group executions together with a run id.
  --run-name TEXT        Name of run (commit, pull request, etc).
  --help                 Show this message and exit.
"""


this_dir = os.path.dirname(os.path.abspath(__file__))
register_benchmarks(this_dir)


def assert_command_output(result, expected):
    assert result.exit_code == 0
    output = result.output.strip().replace("\x08", "")
    assert output == expected.strip()


def test_conbench(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench)
    assert_command_output(result, CONBENCH)


def test_conbench_command_show_result(runner):
    from conbench.cli import conbench

    command = "addition --show-result=true"
    result = runner.invoke(conbench, command)
    assert result.exit_code == 0
    assert "tags" in result.output
    assert "stats" in result.output
    assert "context" in result.output
    assert "machine_info" in result.output


def test_conbench_command_without_cases(runner):
    from conbench.cli import conbench

    command = "addition --show-result=false --show-output=true"
    with unittest.mock.patch("conbench.util.Connection.publish"):
        result = runner.invoke(conbench, command)
    assert_command_output(result, CONBENCH_ADDITION)


def test_conbench_command_without_cases_help(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench, "addition --help")
    assert_command_output(result, CONBENCH_ADDITION_HELP)


def test_conbench_command_with_cases(runner):
    from conbench.cli import conbench

    case = "--rows=2 --columns=10"
    command = f"matrix {case} --show-result=false --show-output=true"
    with unittest.mock.patch("conbench.util.Connection.publish"):
        result = runner.invoke(conbench, command)
    assert_command_output(result, CONBENCH_MATRIX)


def test_conbench_command_with_cases_help(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench, "matrix --help")
    assert_command_output(result, CONBENCH_MATRIX_HELP)


def test_conbench_command_external(runner):
    from conbench.cli import conbench

    command = "external --show-result=false --show-output=true"
    with unittest.mock.patch("conbench.util.Connection.publish"):
        result = runner.invoke(conbench, command)
    assert_command_output(result, CONBENCH_EXTERNAL)


def test_conbench_command_external_help(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench, "external --help")
    assert_command_output(result, CONBENCH_EXTERNAL_HELP)


def test_conbench_list(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench, "list")
    assert_command_output(result, CONBENCH_LIST)
