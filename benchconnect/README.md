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

## Environment variables

benchconnect relies on a number of environment variables to obtain various
metadata:

- `CONBENCH_URL`: Required. The URL of the Conbench server without a trailing
slash, e.g. `https://conbench.example.com`
- `CONBENCH_EMAIL`: The email to use for Conbench login. Only required if the
server is private.
- `CONBENCH_PASSWORD`: The password to use for Conbench login. Only required
if the server is private.
- `CONBENCH_PROJECT_REPOSITORY`: The repository name (in the format `org/repo`) or the
URL (in the format `https://github.com/org/repo`)
- `CONBENCH_PROJECT_PR_NUMBER`: [recommended] The number of the GitHub pull request that
is running this benchmark. Do not supply this for a runs on the default branch.
- `CONBENCH_PROJECT_COMMIT`: The 40-character commit SHA of the repo being benchmarked
- `CONBENCH_MACHINE_INFO_NAME`: By default, the running machine host name (sent in
`machine_info.name` when posting runs and benchmarks) will be obtained with
`platform.node()`, but in circumstances where consistency is needed (e.g.
running in CI or on cloud runners), a value for host name can be specified via
this environment variable instead.

## Usage

### Benchmark run workflow

To submit a run of benchmark results to a Conbench server, benchconnect can
open a run, modify submitted results to be a part of that run, and close it.

A minimal example:

```shell
benchconnect start run '{"run_reason": "test"}'

# pass one result or a whole set at a time, inline or from files
benchconnect submit result --path my-results/

benchconnect finish run
```

Additional metadata can be passed via JSON, e.g. `name` and `github` when
creating the run, or `error_type` and `error_info` when closing it.

### Manual API

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
