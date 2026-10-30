from importlib.metadata import version

import pytest
from typer.testing import CliRunner

from drumtx.cli import app

runner = CliRunner()
COMMANDS = ["transcribe", "render", "preview", "evaluate", "models", "doctor"]


def test_help_lists_every_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in COMMANDS:
        assert command in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"drumtx {version('drumtx')}"


@pytest.mark.parametrize("command", COMMANDS)
def test_stub_commands_fail_clearly(command: str) -> None:
    result = runner.invoke(app, [command])
    assert result.exit_code == 1
    assert f"drumtx {command}: not implemented yet." in result.stderr
