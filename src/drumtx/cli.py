"""DrumTx command-line interface."""

import json
import logging
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from drumtx import pipeline
from drumtx.detect import Preset
from drumtx.errors import DrumtxError, InputError
from drumtx.ingest import DEFAULT_MAX_DURATION_S

log = logging.getLogger("drumtx")

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


def _setup_logging(verbose: bool, quiet: bool) -> None:
    handler = logging.StreamHandler()  # stderr, so stdout stays free for data
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.handlers[:] = [handler]
    log.propagate = False
    log.setLevel(logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO)


def _run(verbose: bool, work: Callable[[], object]) -> None:
    """Run `work`, turning errors into a message and the exit code from §4."""
    try:
        work()
    except DrumtxError as e:
        log.error("Error: %s", e)
        raise typer.Exit(e.exit_code) from None
    except Exception as e:
        if verbose:
            log.exception("Unexpected error")
        else:
            log.error(
                "Unexpected error: %s: %s\nRun again with -v for details, and report it at "
                "https://github.com/tylermac92/drumtx/issues.",
                type(e).__name__,
                e,
            )
        raise typer.Exit(1) from None


@app.command(help="Full pipeline: audio to score, MIDI, events, and report.")
def transcribe(
    audio: Annotated[Path, typer.Argument(metavar="INPUT", help="Audio file to transcribe.")],
    out_dir: Annotated[
        Path | None,
        typer.Option(
            "-o", "--out-dir", help="Output folder.", show_default="./<input name>_drumtx/"
        ),
    ] = None,
    start: Annotated[
        float | None, typer.Option(help="Excerpt start, in seconds from the start of the file.")
    ] = None,
    end: Annotated[
        float | None, typer.Option(help="Excerpt end, in seconds from the start of the file.")
    ] = None,
    max_duration: Annotated[
        float, typer.Option(help="Longest audio accepted, in seconds.")
    ] = DEFAULT_MAX_DURATION_S,
    sensitivity: Annotated[
        Preset,
        typer.Option(
            help="strict misses more hits but adds fewer false ones; sensitive the opposite."
        ),
    ] = "balanced",
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Ignore cached stage outputs and recompute.")
    ] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="More detail.")] = False,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Errors only.")] = False,
) -> None:
    _setup_logging(verbose, quiet)
    config = pipeline.Config(
        input=audio,
        out_dir=out_dir or Path(f"{audio.stem}_drumtx"),
        start=start,
        end=end,
        max_duration=max_duration,
        sensitivity=sensitivity,
        no_cache=no_cache,
    )
    _run(verbose, lambda: pipeline.run(pipeline.RunContext.create(config)))


@app.command(help="Accuracy of predictions against a reference (MIDI or CSV).")
def evaluate(
    pred: Annotated[Path, typer.Option(help="Predicted events: events.json or events.csv.")],
    ref: Annotated[
        Path, typer.Option(help="Reference: MIDI (channel 10, General MIDI drums) or CSV.")
    ],
    ref_beats: Annotated[
        Path | None, typer.Option(help="Reference beats CSV (time_s,beat), for beat metrics.")
    ] = None,
    tolerance_ms: Annotated[
        list[float] | None,
        typer.Option(help="Onset tolerance in ms; repeat for several.", show_default="50, 30"),
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="Also write the results to OUT.json and OUT.md.")
    ] = None,
) -> None:
    from drumtx import evaluate as ev  # mir_eval and SciPy load only for this command

    _setup_logging(verbose=False, quiet=False)

    def work() -> None:
        tolerances = tuple(tolerance_ms or ev.DEFAULT_TOLERANCES_MS)
        if any(t <= 0 for t in tolerances):
            raise InputError(f"--tolerance-ms must be positive, got {tolerances}")
        result = ev.evaluate(
            ev.load_prediction(pred), ev.load_reference(ref, ref_beats), tolerances
        )
        report = ev.markdown(result, pred, ref)
        if out is not None:
            try:
                out.with_name(out.name + ".json").write_text(json.dumps(result, indent=2) + "\n")
                out.with_name(out.name + ".md").write_text(report, encoding="utf-8")
            except OSError as e:
                raise InputError(f"Cannot write {out}.json / .md: {e.strerror}") from e
        typer.echo(report, nl=False)

    _run(False, work)


# The other commands from the Technical Design Document §4 are stubs until their milestones land.
_COMMANDS = {
    "render": "Re-quantize and re-render from an (edited) events JSON or CSV.",
    "preview": "Mix the original audio with synthesized detected hits.",
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
