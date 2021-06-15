import os

from alembic import command
from alembic.config import Config
from sqlalchemy.exc import InvalidRequestError

from ...db import Session
from ...entities.case import Case
from ...entities.context import Context


this_dir = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(this_dir, "../../../alembic.ini")


def test_upgrade():
    case_1 = Case.create(
        {
            "name": "case 1",
            "tags": {
                "dataset": "nyctaxi_sample",
                "cpu_count": 2,
                "file_type": "parquet",
                "gc_collect": True,
                "gc_disable": True,
                "input_type": "arrow",
                "compression": "snappy",
            },
        }
    )
    case_2 = Case.create(
        {
            "name": "case 2",
            "tags": {
                "dataset": "nyctaxi_sample",
                "cpu_count": 2,
                "file_type": "parquet",
                "input_type": "arrow",
                "compression": "snappy",
            },
        }
    )
    context_1 = Context.create(
        {
            "tags": {
                "arrow_compiler_version": "9.3.0",
                "arrow_version": "4.0.0",
                "benchmark_language": "C++",
                "arrow_git_revision": "d5fd3b497c4254ec18bea5943bb9920d0",
            },
        }
    )
    context_2 = Context.create(
        {
            "tags": {
                "arrow_compiler_version": "9.3.0",
                "arrow_version": "4.0.0",
                "benchmark_language": "C++",
            },
        }
    )

    # do migration
    alembic_config = Config(config_path)
    command.stamp(alembic_config, "4a5177dc4e44")
    command.upgrade(alembic_config, "8411faeebc1f")

    # assert after migration
    try:
        Session.refresh(case_1)
    except InvalidRequestError:
        pass  # deleted
    Session.refresh(case_2)
    try:
        Session.refresh(context_1)
    except InvalidRequestError:
        pass  # deleted
    Session.refresh(context_2)
