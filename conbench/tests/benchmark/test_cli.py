import os

from ...util import register_benchmarks


CONBENCH = """
Usage: conbench [OPTIONS] COMMAND [ARGS]...

  Conbench: Language-independent Continuous Benchmarking (CB) Framework

Options:
  --help  Show this message and exit.

Commands:
  addition     Run addition benchmark.
  compare      Compare benchmark runs.
  subtraction  Run subtraction benchmark(s).
"""


CONBENCH_COMPARE = """
TODO
"""


CONBENCH_COMPARE_HELP = """
Usage: conbench compare [OPTIONS] BASELINE CONTENDER

  Compare benchmark runs.

Options:
  --kind [batch|benchmark|run]  [default: batch]
  --threshold INTEGER           (percent)  [default: 5]
  --help                        Show this message and exit.
"""


CONBENCH_ADDITION = """
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


Benchmark output:
2
"""


CONBENCH_ADDITION_HELP = """
Usage: conbench addition [OPTIONS]

  Run addition benchmark.

Options:
  --iterations INTEGER   [default: 1]
  --gc-collect BOOLEAN   [default: true]
  --gc-disable BOOLEAN   [default: true]
  --show-result BOOLEAN  [default: true]
  --show-output BOOLEAN  [default: false]
  --run-id TEXT          Group executions together with a run id.
  --help                 Show this message and exit.
"""


CONBENCH_SUBTRACTION = """
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


Benchmark output:
99
"""


CONBENCH_SUBTRACTION_HELP = """
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
  --all BOOLEAN                [default: false]
  --count INTEGER              [default: 1]
  --iterations INTEGER         [default: 1]
  --gc-collect BOOLEAN         [default: true]
  --gc-disable BOOLEAN         [default: true]
  --show-result BOOLEAN        [default: true]
  --show-output BOOLEAN        [default: false]
  --run-id TEXT                Group executions together with a run id.
  --help                       Show this message and exit.
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
    result = runner.invoke(conbench, command)
    try:
        assert_command_output(result, CONBENCH_ADDITION)
    except AssertionError:
        assert result.output == "\nBenchmark output:\n2\n"


def test_conbench_command_without_cases_help(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench, "addition --help")
    assert_command_output(result, CONBENCH_ADDITION_HELP)


def test_conbench_command_with_cases(runner):
    from conbench.cli import conbench

    case = "sample --color=pink --fruit=apple"
    command = f"subtraction {case} --show-result=false --show-output=true"
    result = runner.invoke(conbench, command)
    try:
        assert_command_output(result, CONBENCH_SUBTRACTION)
    except AssertionError:
        assert result.output == "\nBenchmark output:\n99\n"


def test_conbench_command_with_cases_help(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench, "subtraction --help")
    assert_command_output(result, CONBENCH_SUBTRACTION_HELP)


def test_conbench_compare(runner):
    from conbench.cli import conbench

    baseline_id, contender_id = None, None  # TODO
    result = runner.invoke(conbench, f"compare {baseline_id} {contender_id}")
    # TODO assert_command_output(result, TODO)


def test_conbench_compare_help(runner):
    from conbench.cli import conbench

    result = runner.invoke(conbench, "compare --help")
    assert_command_output(result, CONBENCH_COMPARE_HELP)
