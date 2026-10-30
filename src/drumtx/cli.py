"""DrumTx command-line interface."""

from collections.abc import Callable
from importlib.metadata import version
from typing import Annotated

import typer

app = typer.Typer(help="Drum transcription from audio to editable notation.", no_args_is_help=True)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"drumtx {version('drumtx')}")
        raise typer.Exit()


@app.callback()
def main(
    show_version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_show_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    """Drum transcription from audio to editable notation."""


# Commands from the Technical Design Document §4. Each is a stub until its milestone lands.
_COMMANDS = {
    "transcribe": "Full pipeline: audio to score, MIDI, events, and report.",
    "render": "Re-quantize and re-render from an (edited) events JSON or CSV.",
    "preview": "Mix the original audio with synthesized detected hits.",
    "evaluate": "Accuracy of predictions against a reference (MIDI or CSV).",
    "models": "Manage model files (for offline use).",
    "doctor": "Check the environment: Python, decoders, FFmpeg, extras, models.",
}


def _stub(name: str) -> Callable[[], None]:
    def command() -> None:
        typer.echo(f"drumtx {name}: not implemented yet.", err=True)
        raise typer.Exit(1)

    return command


for _name, _help in _COMMANDS.items():
    app.command(_name, help=_help)(_stub(_name))
