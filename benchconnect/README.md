# benchconnect

A small Python package that creates a CLI for benchmark runners interacting
with a Conbench server.

This is a light wrapper on top of
[benchadapt.BenchmarkResult](https://github.com/conbench/conbench/blob/main/benchadapt/python/benchadapt/result.py),
[benchadapt.BenchmarkRun](https://github.com/conbench/conbench/blob/main/benchadapt/python/benchadapt/run.py), and
[benchclients.ConbenchClient](https://github.com/conbench/conbench/blob/main/benchclients/python/benchclients/conbench.py).
If your code is already in Python, it may be simpler to use those classes
directly.

## Installation

With [pipx](https://pypa.github.io/pipx/):

```bash
pipx install benchconnect@git+https://github.com/conbench/conbench.git@main#subdirectory=benchconnect
```

## Usage

See the man pages:

```shell
benchconnect --help
benchconnect augment --help
benchconnect post --help
benchconnect put --help
```

The `augment` command takes JSON for a benchmark result (`augment result`)
or benchmark run (`augment run`) and fills in defaults for unspecified fields.
This is useful for filling in fields like `machine_info` consistently. Note
this is stateless, and will not make `run_id` and `suite_id` values correspond
across results, nor will the resulting JSON necessarily be complete enough to
post to a Conbench server correctly (it can't fill in things like `run_reason`
for you); please ensure data is correct before posting.

The `post` and `put` commands authenticate with a Conbench server (see man
pages for environment variables) and send JSON passed. Since they correspond
to the API, there are `post result` and `post run` methods, but only `put run`.
