import pytest
from click.testing import CliRunner

from benchconnect._cli import augment, cli, post, put

runner = CliRunner()


@pytest.mark.parametrize("command", [cli, augment, post, put])
@pytest.mark.parametrize("args", [[], ["--help"]])
def test_help(command, args: list) -> None:
    res = runner.invoke(command, args=args)
    assert res.exit_code == 0
    assert res.output
