"""M0-5 spike: can Beat This! run without PyTorch? Export the model to ONNX and compare outputs.

python onnx_check.py final0   # spike-venv
"""

import sys
import time

import numpy as np
import onnxruntime as ort
import soxr
import torch
from beat_this.inference import LogMelSpect, load_audio, load_model
from track import DATA, clips


class Logits(torch.nn.Module):
    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, spect: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        out = self.model(spect)
        return out["beat"], out["downbeat"]


def main(checkpoint: str) -> None:
    model = Logits(load_model(checkpoint, device="cpu")).eval()
    path = DATA / "models" / "beat_this" / f"{checkpoint}.onnx"
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        (torch.zeros(1, 1500, 128),),
        str(path),
        input_names=["spect"],
        output_names=["beat", "downbeat"],
        dynamic_axes={"spect": {1: "frames"}},
        opset_version=17,
        dynamo=False,
    )
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    spect_fn = LogMelSpect()
    worst = 0.0
    t_torch = t_onnx = 0.0
    for r in clips()[:6]:
        audio, sr = load_audio(str(DATA / r["audio"]))
        audio = soxr.resample(audio.mean(axis=1) if audio.ndim == 2 else audio, sr, 22050)
        spect = spect_fn(torch.tensor(audio, dtype=torch.float32))[None, :1500]
        t0 = time.perf_counter()
        with torch.no_grad():
            want = [t.numpy() for t in model(spect)]
        t_torch += time.perf_counter() - t0
        t0 = time.perf_counter()
        got = session.run(None, {"spect": spect.numpy()})
        t_onnx += time.perf_counter() - t0
        worst = max(worst, *(float(np.abs(w - g).max()) for w, g in zip(want, got, strict=True)))
    size = path.stat().st_size / 1e6
    print(f"{checkpoint}: onnx {size:.1f} MB, max |torch - onnx| logit {worst:.2e}")
    print(f"torch {t_torch:.2f}s vs onnx {t_onnx:.2f}s for 6 x 30 s chunks")


if __name__ == "__main__":
    main(sys.argv[1])
