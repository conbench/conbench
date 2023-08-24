import logging

import click
from benchclients.logging import log

import benchconnect._augment as _augment
import benchconnect._finish as _finish
import benchconnect._post as _post
import benchconnect._start as _start
import benchconnect._submit as _submit
from benchconnect.utils import ENV_VAR_HELP

log.setLevel(logging.DEBUG)


@click.group(help="Command line utilities for interacting with a Conbench API")
def cli():
    pass


@cli.group(help="Fill in missing fields of a JSON blob with defaults")
def augment():
    pass


augment.add_command(_augment.result, name="result")


@cli.group(help="Post something to a Conbench API" + ENV_VAR_HELP)
def post():
    pass


post.add_command(_post.result, name="result")


@cli.group(help="Start a stateful operation" + ENV_VAR_HELP)
def start():
    pass


start.add_command(_start.start_run, name="run")


@cli.group(help="Submit to an active stateful operation" + ENV_VAR_HELP)
def submit():
    pass


submit.add_command(_submit.submit_result, name="result")


@cli.group(help="End a stateful operation" + ENV_VAR_HELP)
def finish():
    pass


finish.add_command(_finish.finish_run, name="run")
