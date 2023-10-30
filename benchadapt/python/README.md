# Python {benchadapt}

A small python package with utilities for getting benchmark results into a Conbench server.

## Useful components in this package

### `BenchmarkResult` dataclass

The `BenchmarkResult` dataclass is designed to make it easy to
populate JSON payloads to post to a Conbench server. The structure corresponds to the
corresponding POST endpoint; it has a `.to_publishable_dict()` method that
produces a dict to post.

Regardless of how you are using it, the docstrings of this object will be useful
as you try to assemble your results to get them in Conbench. All fields are documented,
as are interactions between them and what you likely need to specify.

The object tries to help you fill in your payloads correctly, including some defaults,
like populating `machine_info` with metadata on the current machine. If you are running
on a cluster instead, you will need to populate `cluster_info` yourself, and
`machine_info` will remain empty.

There is light validation, but [for now] the API is the ultimate validator; it is
possible to make payloads that will be rejected.

If you need to interact directly with a Conbench webapp's API instead of letting adapters
(see below) or another tool manage sending results for you, you can use
[benchclients.ConbenchClient](https://github.com/conbench/conbench/blob/main/benchclients/python/benchclients/conbench.py)
to make requests. As benchclients is a dependency of benchadapt, you should not need to
install anything new, and it is nicely set up to handle auth and such for you.

### Adapters

The concept of Conbench adapters is for when you already have a benchmarking method that
produces a pile of results (say in JSON files, though anything works), and you need to
transform them into an appropriate form that can be posted to a Conbench API.

The `benchadapt.adapters.BenchmarkAdapter` abstract class defines a basic workflow:

1. Call an arbitrary `command` shell command, presumably to run benchmarks. If results
are already guaranteed to exist, this can be set to do nothing.
2. Transform results produced by the benchmarks into a list of `BenchmarkResult` instances.
3. Postprocess results to ensure a consistent `run_id` and override any metadata fields
not already set correctly.
4. Post each result to a Conbench API.

Classes that inherit from the abstract class need to define

1. How to get results, including what `command` should be (though it can be defined later
by the user, if desired) and how to get the raw results (e.g. if they are in a file or
directory of files, where they are and how to read them in).
2. How to transform the results into a list of `BenchmarkResult` instances ((2) above) in
the `._transform_results()` method.

(3) and (4) are handled by the abstract class.

Various adapters are alrady defined in the `adapters` submodule, including ones for
Google Benchmark and Folly, as well as a generic `CallableAdapter`, which takes a Python
`Callable` instance (a function or class with a `__call__()` method) that returns a list
of `BenchmarkResult` instances directly instead of a shell command. Many more adapters
are possible; if you create one corresponding to a benchmarking tool, please make a PR!

#### Running an adapter

Adapters have separate `.run()` and `.post_results()` methods; the former runs the
benchmarks, transforms the results, and stores them in a `.results` attribute of the
instance. It does not post them, so is useful for looking at results interactively before
sending them. `.post_results()` takes the results from the `.results` attribute and
posts them to a Conbench API.

The whole instance also has a `__call__()` method defined so it can be called like a
function that both runs and publishes, so a somewhat minimal script for running
benchmarks in CI might look like

``` python
import os

from benchadapt.adapters import GoogleBenchmarkAdapter

adapter = GoogleBenchmarkAdapter(
    command=["bash", "./run-benchmarks.sh"],
    result_file="benchmarks.json",
    result_fields_override={
        "run_reason": os.getenv("CONBENCH_RUN_REASON")
    },
    result_fields_append={
        "info": {"build_version": os.getenv("MY_BUILD_VERSION")},
        "context": {"compiler_flags": os.getenv("MY_COMPILER_FLAGS")}
    }
)
adapter()
```

Of note:

- `result_fields_override` will replace the whole attribute with a new value. This works
with all types (strings, dicts, etc.), so here `run_reason` will be set for all results.
- `result_fields_append` will append the new values to dicts which may already have data.
Here, `build_version` will be appended to the `info` dict. In this case it is an empty
dict anyway, so this is equivalent to
`result_fields_override={"info": {"build_version": os.getenv("MY_BUILD_VERSION")}})`.
But the `context` dict will already contain a `"benchmark_language"` key; this will be
retained, and `compiler_flags` will be appended.
- For this to work, a lot of environment variables have to be set! This includes ones
with information about the Conbench server and the current git metadata. See the
"Environment Variables" section below for a full list.


## Environment variables

Some operations of benchadapt rely on a number of environment variables. The Conbench API
ones (`CONBENCH_*`) are used by `benchclients.ConbenchClient`; the git ones
(`CONBENCH_PROJECT_*`) are used to populate run and result metadata if not specified
directly; and `CONBENCH_MACHINE_INFO_NAME` is for overriding the machine name in
automatically gathered machine info when necessary:

- `CONBENCH_URL`: Required. The URL of the Conbench API without a trailing
slash, e.g. `https://conbench.example.com`
- `CONBENCH_EMAIL`: The email to use for Conbench login
- `CONBENCH_PASSWORD`: The password to use for Conbench login
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
