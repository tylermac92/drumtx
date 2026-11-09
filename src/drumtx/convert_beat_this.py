# mypy: disallow-subclassing-any=False
"""Convert the Beat This! `final0` checkpoint to ONNX (M3-1; decision 0006).

Never imported by DrumTx: `drumtx models download beat-this-final0` runs it once, in a throwaway
environment that uv builds with the `beat-this` package and PyTorch (drumtx.models), after the
checkpoint's SHA-256 has been checked. `beat_this` reads it with `torch.load(weights_only=True)`,
which reads tensors and plain values only. DrumTx itself runs only the ONNX file.
"""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from beat_this.inference import load_model


class Logits(torch.nn.Module):
    """The network with plain outputs: beat and downbeat logits per frame."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, spect: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        out = self.model(spect)
        return out["beat"], out["downbeat"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--model-dir", type=Path, required=True)
    folder = p.parse_args().model_dir
    model = Logits(load_model(str(folder / "final0.ckpt"), device="cpu")).eval()
    out = folder / "beat_this_final0.onnx"
    torch.onnx.export(
        model,
        (torch.zeros(1, 1500, 128),),
        str(out),
        input_names=["spect"],
        output_names=["beat", "downbeat"],
        dynamic_axes={"spect": {1: "frames"}},
        opset_version=17,
        # Not EVAL: it folds BatchNorm into the convolutions with this CPU's vector kernels, so
        # the weights (and the SHA-256) differ in the last bit between machines. The model is in
        # eval mode, so PRESERVE still exports inference mode, with the checkpoint's own tensors.
        training=torch.onnx.TrainingMode.PRESERVE,
        dynamo=False,
    )
    x = np.random.default_rng(0).random((1, 1500, 128), dtype=np.float32) * 8
    with torch.no_grad():
        want = [t.numpy() for t in model(torch.from_numpy(x))]
    got = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"]).run(None, {"spect": x})
    err = max(float(np.abs(w - g).max()) for w, g in zip(want, got, strict=True))
    print(f"max |ONNX Runtime - PyTorch| logit = {err:.1e}")
    assert err < 1e-3, err
    print(f"wrote {out}\nSHA-256 {hashlib.sha256(out.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
