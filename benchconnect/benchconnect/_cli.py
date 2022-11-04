import logging

import click
from benchclients.logging import log

import benchconnect._augment as _augment
import benchconnect._post as _post
import benchconnect._put as _put

log.setLevel(logging.DEBUG)


@click.group(help="Command line utilities for interacting with a Conbench API")
def cli():
    pass


@cli.group(help="Fill in missing fields of a JSON blob with defaults")
def augment():
    pass


augment.add_command(_augment.result, name="result")
augment.add_command(_augment.run, name="run")


@cli.group(
    help="""
Post something to a Conbench API

\b
Environment variables:
  CONBENCH_URL: The URL of the Conbench server. Required.
  CONBENCH_EMAIL: The email to use for Conbench login. Only required if the server is private.
  CONBENCH_PASSWORD: The password to use for Conbench login. Only required if the server is private.
"""
)
def post():
    pass


post.add_command(_post.result, name="result")
post.add_command(_post.run, name="run")


@cli.group(
    help="""
Put something to a Conbench API

\b
Environment variables:
  CONBENCH_URL: The URL of the Conbench server. Required.
  CONBENCH_EMAIL: The email to use for Conbench login. Only required if the server is private.
  CONBENCH_PASSWORD: The password to use for Conbench login. Only required if the server is private.
"""
)
def put():
    pass


put.add_command(_put.run, name="run")
