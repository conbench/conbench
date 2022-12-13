import json
import logging
import math


import click
import sigfig

from . import __version__
from .runner import LIST, REGISTRY
from .util import register_benchmarks


log = logging.getLogger(__name__)

register_benchmarks()
BENCHMARKS = {}
for benchmark in REGISTRY:
    BENCHMARKS[benchmark.name] = benchmark


if not BENCHMARKS:
    click.echo(click.style("\nNo benchmarks registered.", fg="red"))
    tip_msg = "(run conbench from a directory containing benchmarks).\n"
    click.echo(click.style(tip_msg, fg="yellow"))


@click.group()
def conbench():
    """Conbench: Language-independent Continuous Benchmarking (CB) Framework"""
    pass


@conbench.command(name="list")
def list_benchmarks():
    """List of benchmarks (for orchestration)."""
    benchmarks = []
    if LIST:
        benchmarks = LIST[0]().list(BENCHMARKS)
    print(json.dumps(benchmarks, indent=2))


@conbench.command(name="version")
def version():
    """Display Conbench version."""
    print(f"conbench version: {__version__}")


def _option(params, name, default, _type, help_msg=None):
    params.append(
        click.Option(
            (name,),
            type=_type,
            default=default,
            help=help_msg,
            show_default=True,
        )
    )


def _choice(params, name, choices):
    params.append(
        click.Option(
            (name,),
            default=str(choices[0]),
            show_default=False,
            type=click.Choice([str(c) for c in choices], case_sensitive=False),
        )
    )


def _help(benchmark, name, cases, tags):
    if not cases:
        description = getattr(benchmark, "description", f"Run {name} benchmark.")
        return description

    valid = [list(zip(tags, case)) for case in cases]
    benchmarks = [[f"{option}={value}" for option, value in case] for case in valid]
    examples = "\b\n".join([" ".join(example) for example in benchmarks])
    description = getattr(benchmark, "description", f"Run {name} benchmark(s).")
    examples = f"\b\nValid benchmark combinations:\n{examples}"
    note = "For each benchmark option, the first option value is the default."
    all_cases = f"\b\nTo run all combinations:\n$ conbench {name} --all=true"
    return f"{description}\n\n{note}\n\n{examples}\n\n{all_cases}"


def _to_cli_name(name):
    return f"--{name.replace('_', '-')}"


def log_timing_report_across_results(results):
    # Find tags that are common among all results. That makes sense only when
    # there is more than one result.
    if len(results) == 1:
        common_tag_keys = []
    else:
        common_tags = set.intersection(*tuple(set(r["tags"].items()) for r in results))
        common_tag_keys = [t[0] for t in common_tags]
        log.info("common tag keys across results: %s", common_tag_keys)

    # For each result, assemble a human-readable string which represents the
    # case/scenario from the tags. Also assemble a human-readable string that
    # reports the timing info for this scenario.
    tagstrings = []
    timestrings = []

    for r in results:
        tags = r["tags"]

        # That represents the case/senario. Note that `tags` has been enriched
        # with key/value pairs beyond the case -- filter these out again.
        tagstring = ", ".join(
            f"{k}: {tags[k]}" for k in sorted(tags.keys()) if k not in common_tag_keys
        )

        # Assume that stdev=0 for now means there is only one sample.
        if r["stats"]["stdev"] == 0:
            timestring = f"{sigfig.round(r['stats']['data'][0], 2)} s"
        else:
            # Assume that there are at least three samples. Standard deviation
            # is known, calc standard error of the mean:
            mean = r["stats"]["mean"]
            stdev = r["stats"]["stdev"]
            min = r["stats"]["min"]
            stdem = float(stdev) / math.sqrt(len(r["stats"]["data"]))
            minstr = f"min: {sigfig.round(min, 3)} s"

            # This generates a string like '3.1 ± 0.7'
            mean_unc_str = sigfig.round(mean, uncertainty=stdem)
            timestring = f"{minstr.ljust(15)} mean±SE: ({mean_unc_str}) s"

        tagstrings.append(tagstring)
        timestrings.append(timestring)

        # TODO: do not do this when distribution is multimodal. But now that
        # we're also printing the min value a human can quickly detect some
        # situations where the min appears far off the mean.

    msg = ""
    for tagstring, timestring in zip(tagstrings, timestrings):
        msg += f"{tagstring}\n    --> {timestring}\n"

    log.info("result timing overview:\n\n%s", msg)


for name, benchmark in BENCHMARKS.items():
    params = []

    instance = benchmark()
    fields, cases = instance.fields, instance.cases
    options = getattr(benchmark, "options", {})
    arguments = getattr(benchmark, "arguments", [])
    tags = [_to_cli_name(tag) for tag in fields]
    external = getattr(benchmark, "external", False)

    for k, v in instance.case_options.items():
        _choice(params, _to_cli_name(k), sorted(v))

    for argument in arguments:
        params.append(click.Argument((argument,)))
    if cases:
        _option(params, "--all", "false", bool)
    for option, config in options.items():
        if "choices" in config:
            _choice(params, _to_cli_name(option), config["choices"])
        else:
            help_msg = config.get("help", None)
            _option(
                params,
                _to_cli_name(option),
                config.get("default"),
                config["type"],
                help_msg=help_msg,
            )
    if not external:
        _option(params, "--iterations", 1, int)
        _option(params, "--drop-caches", "false", bool)
        _option(params, "--gc-collect", "true", bool)
        _option(params, "--gc-disable", "true", bool)
    _option(params, "--show-result", "true", bool)
    _option(params, "--show-output", "false", bool)

    params.append(
        click.Option(
            ("--run-id",),
            type=str,
            help="Group executions together with a run id.",
        )
    )
    params.append(
        click.Option(
            ("--run-name",),
            type=str,
            help="Free-text name of run (commit ABC, pull request 123, etc).",
        )
    )
    params.append(
        click.Option(
            ("--run-reason",),
            type=str,
            help="Low-cardinality reason for run (commit, pull request, manual, etc).",
        )
    )

    def _benchmark(
        show_result,
        show_output,
        benchmark=benchmark,
        **kwargs,
    ):
        results = []

        for result, output in benchmark().run(**kwargs):

            results.append(result)
            if show_output:
                click.echo()
                click.echo(click.style("Benchmark output:", fg="yellow"))
                click.echo(click.style(str(output), fg="blue"))
            if show_result:
                click.echo()
                click.echo(click.style("Benchmark result:", fg="yellow"))
                json_result = json.dumps(result, indent=4, sort_keys=True)
                if "error" in json_result:
                    click.echo(click.style(json_result, fg="red"))
                else:
                    click.echo(click.style(json_result, fg="green"))
            del output

        log_timing_report_across_results(results)

    conbench.add_command(
        click.Command(
            name,
            params=params,
            callback=_benchmark,
            help=_help(benchmark, name, cases, tags),
        )
    )
