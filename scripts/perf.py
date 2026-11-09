"""Time `drumtx transcribe` and measure its peak memory (M6-1, Technical Design Document §11).

    uv run python scripts/perf.py AUDIO [AUDIO ...] [--runs 3] [--separate] [--out FILE]

Each run is `drumtx transcribe AUDIO --no-cache -v` in a fresh process, into a temporary folder,
timed from start to exit (decision 0008). The process reports its own peak memory (resident set
on Linux and macOS, peak working set on Windows). Per audio file: the median wall time of the
runs, as a share of the audio's length (the real-time factor), the median time of each stage
(from -v), and the highest peak memory. Download the models first. Writes JSON and Markdown
(default eval/results/perf-<machine>.json and .md) and prints the Markdown.
"""

import argparse
import datetime
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import soundfile as sf

PEAK = "PERF_PEAK_BYTES"


def peak_bytes() -> int:
    """This process's peak memory so far."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        # Declared types: by default ctypes passes the 64-bit process handle as a 32-bit int.
        current = ctypes.windll.kernel32.GetCurrentProcess
        current.restype = wintypes.HANDLE
        info = ctypes.windll.psapi.GetProcessMemoryInfo
        info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        info.restype = wintypes.BOOL
        c = Counters()
        c.cb = ctypes.sizeof(c)
        if not info(current(), ctypes.byref(c), c.cb):
            raise ctypes.WinError()
        return int(c.PeakWorkingSetSize)
    import resource

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform == "darwin" else rss * 1024)  # bytes on macOS, KB on Linux


def child(args: list[str]) -> None:
    """Run the CLI in this process, then report the peak memory."""
    from drumtx.cli import app

    code = 0
    try:
        app(args, prog_name="drumtx")
    except SystemExit as e:
        code = int(e.code or 0)
    print(f"{PEAK} {peak_bytes()}", flush=True)
    sys.exit(code)


def run_once(audio: Path, separate: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as out:
        cmd = [sys.executable, __file__, "--child", "transcribe", str(audio), "-o", out]
        cmd += ["--no-cache", "-v", *["--separate"] * separate]
        start = time.perf_counter()
        p = subprocess.run(cmd, capture_output=True, text=True)
        wall = time.perf_counter() - start
    if p.returncode != 0:
        sys.exit(f"transcribe failed on {audio}:\n{p.stderr}")
    names = re.findall(r"^\[\d+/\d+\] (\w+)", p.stderr, re.M)
    seconds = [float(s) for s in re.findall(r"^\s+key \w+, ([\d.]+) s$", p.stderr, re.M)]
    peak = int(re.findall(rf"^{PEAK} (\d+)$", p.stdout, re.M)[-1])
    return {"wall_s": wall, "stages": dict(zip(names, seconds, strict=True)), "peak": peak}


def markdown(result: dict[str, Any]) -> str:
    m = result["machine"]
    lines = [
        "# DrumTx performance",
        "",
        f"- Machine: {m['processor']}, {m['cpus']} logical CPUs, {m['platform']}",
        f"- Python {m['python']}, commit {result['commit']}, {result['date']}",
        f"- `drumtx transcribe --no-cache`, {result['runs']} runs per file, median",
        "",
        "| File | Audio | Separate | Wall time | Real-time factor | Peak memory | Stages |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in result["files"]:
        stages = ", ".join(f"{k} {v:.1f} s" for k, v in f["stages_s"].items())
        lines.append(
            f"| {f['file']} | {f['audio_s'] / 60:.1f} min | {'yes' if f['separate'] else 'no'} "
            f"| {f['wall_s']:.1f} s | {f['realtime_factor']:.3f} | {f['peak_mb']:,} MB "
            f"| {stages} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    if sys.argv[1:2] == ["--child"]:
        child(sys.argv[2:])
    from benchmark import REPO, commit  # not at the top: the measured child must not load it

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("audio", type=Path, nargs="+")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--separate", action="store_true", help="time --separate (needs the extra)")
    p.add_argument("--out", type=Path, help="results JSON; .md is written beside it")
    args = p.parse_args()
    files = []
    for audio in args.audio:
        runs = [run_once(audio, args.separate) for _ in range(args.runs)]
        audio_s = sf.info(audio).duration
        wall = statistics.median(r["wall_s"] for r in runs)
        files.append(
            {
                "file": audio.name,
                "audio_s": round(audio_s, 1),
                "separate": args.separate,
                "wall_s": round(wall, 2),
                "realtime_factor": round(wall / audio_s, 4),
                "runs_s": [round(r["wall_s"], 2) for r in runs],
                "stages_s": {
                    k: round(statistics.median(r["stages"][k] for r in runs), 2)
                    for k in runs[0]["stages"]
                },
                "peak_mb": round(max(r["peak"] for r in runs) / 2**20),
            }
        )
    result = {
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor() or platform.machine(),
            "cpus": os.cpu_count(),
            "python": platform.python_version(),
        },
        "commit": commit(),
        "date": datetime.date.today().isoformat(),
        "runs": args.runs,
        "files": files,
    }
    name = re.sub(r"[^\w-]", "-", platform.node().lower()) or "machine"
    out = args.out or REPO / "eval" / "results" / f"perf-{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    out.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print(markdown(result))


if __name__ == "__main__":
    main()
