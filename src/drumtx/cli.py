"""DrumTx command-line interface."""

import json
import logging
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from drumtx import models, pipeline, render, separate
from drumtx.detect import Preset
from drumtx.errors import DrumtxError, InputError
from drumtx.ingest import DEFAULT_MAX_DURATION_S
from drumtx.midi import MidiTiming
from drumtx.quantize import GridOption

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


def _beats_per_bar(time_signature: str | None) -> int | None:
    """N from "N/4"; anything else is a usage error (exit code 2)."""
    if time_signature is None:
        return None
    n, _, beat_type = time_signature.partition("/")
    if beat_type != "4" or not n.isdigit() or not 1 <= int(n) <= 16:
        typer.echo(
            f"Error: --time-signature must be N/4 with N from 1 to 16, got {time_signature!r}.",
            err=True,
        )
        raise typer.Exit(2)
    return int(n)


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
    bpm: Annotated[
        float | None,
        typer.Option(help="Tempo, to fix half- or double-time beats.", show_default="estimated"),
    ] = None,
    time_signature: Annotated[
        str | None, typer.Option(help="Meter as N/4, e.g. 3/4.", show_default="4/4")
    ] = None,
    first_downbeat: Annotated[
        float | None,
        typer.Option(
            help="Start of bar 1, in seconds from the start of the file.",
            show_default="estimated",
        ),
    ] = None,
    grid: Annotated[
        GridOption, typer.Option(help="Note grid: 16th, triplet, or auto (chosen per beat).")
    ] = "auto",
    midi_timing: Annotated[
        MidiTiming,
        typer.Option(help="MIDI notes on the grid (quantized) or at their detected times."),
    ] = "quantized",
    model: Annotated[
        str,
        typer.Option(
            help="Detection model (`drumtx models list`). baseline needs no download.",
        ),
    ] = models.DEFAULT,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Never access the network; fail if the model is missing."),
    ] = False,
    separate_drums: Annotated[
        bool,
        typer.Option(
            "--separate/--no-separate",
            help="Isolate the drums first (recommended for full mixes). Needs drumtx[separation].",
        ),
    ] = False,
    device: Annotated[
        separate.Device, typer.Option(help="Where --separate runs: cpu, or cuda for an NVIDIA GPU.")
    ] = "cpu",
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Ignore cached stage outputs and recompute.")
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite existing outputs, except an events.csv edited since it was written.",
        ),
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
        model=model,
        offline=offline,
        separate=separate_drums,
        device=device,
        bpm=bpm,
        beats_per_bar=_beats_per_bar(time_signature),
        first_downbeat=first_downbeat,
        grid=grid,
        midi_timing=midi_timing,
        no_cache=no_cache,
        force=force,
    )

    def work() -> None:
        if bpm is not None and not 20 <= bpm <= 400:
            raise InputError(f"--bpm must be between 20 and 400, got {bpm:g}.")
        if first_downbeat is not None and first_downbeat < 0:
            raise InputError(f"--first-downbeat must be 0 or more, got {first_downbeat:g}.")
        # Fail before any slow work: an unknown or non-detector model, a missing extra.
        if model != models.BASELINE and models.spec(model).kind != "detector":
            raise InputError(f"{model} is not a detection model; see `drumtx models list`.")
        if separate_drums:
            separate.check_installed()
        render.check_outputs(config.out_dir, audio.stem, force)  # before any slow work
        pipeline.run(pipeline.RunContext.create(config))

    _run(verbose, work)


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


models_app = typer.Typer(help="Manage model files (for offline use).", no_args_is_help=True)
app.add_typer(models_app, name="models")


@models_app.command("list", help="Available models and whether each is installed.")
def models_list() -> None:
    def status(m: models.Model) -> str:
        return "installed" if (models.cache_dir() / m.file).exists() else "not installed"

    rows = [(models.BASELINE, "classical detector", "built in", "DrumTx")]
    rows += [(m.id, m.version, status(m), m.license) for m in models.REGISTRY.values()]
    for model_id, model_version, state, license_ in rows:
        default = " (default)" if model_id == models.DEFAULT else ""
        typer.echo(f"{model_id + default:<20} {model_version:<22} {state:<14} {license_}")
    typer.echo(f"\nModel directory: {models.cache_dir()}")


@models_app.command("download", help="Download (and verify) a model now, for offline use.")
def models_download(
    model_id: Annotated[
        str, typer.Argument(metavar="MODEL", help="Model ID.", show_default=True)
    ] = models.DEFAULT,
) -> None:
    _setup_logging(verbose=False, quiet=False)

    def work() -> None:
        m = models.spec(model_id)
        path = models.cache_dir() / m.file
        if path.exists():
            try:
                models.get_model(model_id, offline=True)
                log.info("%s is already installed: %s", model_id, path)
                return
            except DrumtxError as e:
                log.warning("Replacing it. %s", e)
        models.download(m)

    _run(False, work)


# The other commands from the Technical Design Document §4 are stubs until their milestones land.
_COMMANDS = {
    "render": "Re-quantize and re-render from an (edited) events JSON or CSV.",
    "preview": "Mix the original audio with synthesized detected hits.",
    "doctor": "Check the environment: Python, decoders, FFmpeg, extras, models.",
}


def _stub(name: str) -> Callable[[], None]:
    def command() -> None:
        typer.echo(f"drumtx {name}: not implemented yet.", err=True)
        raise typer.Exit(1)

    return command


for _name, _help in _COMMANDS.items():
    app.command(_name, help=_help)(_stub(_name))
