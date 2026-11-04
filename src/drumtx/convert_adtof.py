# mypy: disallow-subclassing-any=False, warn-return-any=False
"""Download the ADTOF Frame_RNN checkpoint and convert it to ONNX (M2-1; see docs/models).

Never imported by DrumTx: `drumtx models download adtof` runs it once, in a throwaway environment
that uv builds with TensorFlow and PyTorch (drumtx.models); DrumTx itself needs neither. Steps:
1. Download the checkpoint from a pinned ADTOF commit, unless present, and check its SHA-256.
2. Read it with TensorFlow (a checkpoint holds only tensors, no code) and port it to PyTorch.
3. Check the port against a Keras rebuild of the same network.
4. Export to ONNX and check ONNX Runtime against PyTorch.

The weights are CC BY-NC-SA 4.0 (decision 0003): keep both files out of the repository.
"""

import argparse
import hashlib
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

COMMIT = "b3968fb332f69b65ee07c089fc62f436503755db"
URL = f"https://raw.githubusercontent.com/MZehren/ADTOF/{COMMIT}/adtof/models/"
NAME = "Frame_RNN_adtofAll_0"
SHA256 = {
    f"{NAME}.index": "3fe35e421c448c395984168cd3aa1f979def902df784b6766291e55bb9aa069f",
    f"{NAME}.data-00000-of-00001": (
        "ff611129cb4a4d30722a54251e893341a58a016a40c419ab1e3786fc77a04779"
    ),
}
ONNX_NAME = "frame_rnn_adtof_all_0.onnx"


class SamePool(nn.Module):
    """MaxPool (1, 3) with TensorFlow "same" padding, which splits padding before and after."""

    def __init__(self, bins: int) -> None:
        super().__init__()
        total = -(-bins // 3) * 3 - bins
        self.pad = (total // 2, total - total // 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return nn.functional.max_pool2d(nn.functional.pad(x, self.pad, value=-torch.inf), (1, 3))


class CRNN(nn.Module):
    """ADTOF Frame_RNN: 2 × (2 conv + batch norm, max pool), 3 bidirectional GRUs, sigmoid."""

    def __init__(self) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        c, bins = 1, 84
        for f in (32, 64):
            for c_in in (c, f):
                layers += [nn.Conv2d(c_in, f, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(f, eps=1e-3)]
            layers += [SamePool(bins), nn.Dropout(0.3)]
            c, bins = f, -(-bins // 3)
        self.cnn = nn.Sequential(*layers)
        self.grus = nn.ModuleList(
            nn.GRU(i, 60, batch_first=True, bidirectional=True) for i in (c * bins, 120, 120)
        )
        self.out = nn.Linear(120, 5)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (batch, frames, 84) → (batch, frames, 5)
        x = self.cnn(x[:, None]).permute(0, 2, 3, 1).flatten(2)  # Keras flattens (freq, channel)
        for g in self.grus:
            x, _ = g(x)
        return torch.sigmoid(self.out(x))


def fetch(model_dir: Path) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for name, sha in SHA256.items():
        path = model_dir / name
        if not path.exists():
            print("downloading", URL + name)
            urllib.request.urlretrieve(URL + name, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise SystemExit(f"{path} does not match its SHA-256; delete it and run again.")


def _gru(w: np.ndarray) -> torch.Tensor:
    """Keras gate order (z, r, h) on the last axis → PyTorch (r, z, n) on the first."""
    z, r, h = np.split(w, 3, axis=-1)
    return torch.from_numpy(np.concatenate([r, z, h], axis=-1).T.copy())


def port(v: Any) -> CRNN:
    """Copy the checkpoint's tensors (looked up with `v(name)`) into the PyTorch CRNN."""

    def t(name: str) -> torch.Tensor:
        return torch.from_numpy(np.ascontiguousarray(v(name)))

    model = CRNN().eval()
    convs = [m for m in model.cnn if isinstance(m, nn.Conv2d)]
    norms = [m for m in model.cnn if isinstance(m, nn.BatchNorm2d)]
    for i, (conv, bn) in enumerate(zip(convs, norms, strict=True)):
        p = f"layer_with_weights-0/layer_with_weights-{2 * i}"
        q = f"layer_with_weights-0/layer_with_weights-{2 * i + 1}"
        conv.weight.data = torch.from_numpy(v(p + "/kernel").transpose(3, 2, 0, 1).copy())
        conv.bias.data = t(p + "/bias")
        bn.weight.data, bn.bias.data = t(q + "/gamma"), t(q + "/beta")
        bn.running_mean.data, bn.running_var.data = t(q + "/moving_mean"), t(q + "/moving_variance")
    for i, g in enumerate(model.grus):
        for keras_dir, suffix in (("forward_layer", ""), ("backward_layer", "_reverse")):
            p = f"layer_with_weights-{i + 1}/{keras_dir}/cell"
            b = v(p + "/bias")
            getattr(g, f"weight_ih_l0{suffix}").data = _gru(v(p + "/kernel"))
            getattr(g, f"weight_hh_l0{suffix}").data = _gru(v(p + "/recurrent_kernel"))
            getattr(g, f"bias_ih_l0{suffix}").data = _gru(b[0])
            getattr(g, f"bias_hh_l0{suffix}").data = _gru(b[1])
    model.out.weight.data = torch.from_numpy(v("layer_with_weights-4/kernel").T.copy())
    model.out.bias.data = t("layer_with_weights-4/bias")
    return model


def keras_reference(v: Any, x: np.ndarray) -> np.ndarray:
    """The same network rebuilt in Keras with the checkpoint's weights, run on `x`."""
    from tensorflow import keras

    inp = keras.Input((None, 84, 1))
    h, weights = inp, []
    for i, f in enumerate((32, 64)):
        for j in range(2):
            p = f"layer_with_weights-0/layer_with_weights-{4 * i + 2 * j}"
            q = f"layer_with_weights-0/layer_with_weights-{4 * i + 2 * j + 1}"
            conv = keras.layers.Conv2D(f, 3, padding="same", activation="relu")
            bn = keras.layers.BatchNormalization()
            h = bn(conv(h))
            weights += [
                (conv, [v(p + "/kernel"), v(p + "/bias")]),
                (bn, [v(q + n) for n in ("/gamma", "/beta", "/moving_mean", "/moving_variance")]),
            ]
        h = keras.layers.MaxPool2D((1, 3), padding="same")(h)
    h = keras.layers.Reshape((-1, 640))(h)
    for i in range(3):
        layer = keras.layers.Bidirectional(keras.layers.GRU(60, return_sequences=True))
        h = layer(h)
        ws = []
        for d in ("forward_layer", "backward_layer"):
            p = f"layer_with_weights-{i + 1}/{d}/cell"
            ws += [v(p + "/kernel"), v(p + "/recurrent_kernel"), v(p + "/bias")]
        weights.append((layer, ws))
    dense = keras.layers.Dense(5, activation="sigmoid")
    out = dense(h)
    weights.append((dense, [v("layer_with_weights-4/kernel"), v("layer_with_weights-4/bias")]))
    model = keras.Model(inp, out)
    for layer, ws in weights:
        layer.set_weights(ws)
    return np.asarray(model.predict(x[..., None], verbose=0))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--model-dir", type=Path, default=Path.home() / "drumtx-data/models/adtof")
    args = p.parse_args()
    fetch(args.model_dir)

    import onnxruntime as ort
    import tensorflow as tf

    ckpt = tf.train.load_checkpoint(str(args.model_dir / NAME))

    def v(name: str) -> np.ndarray:
        return np.asarray(ckpt.get_tensor(name + "/.ATTRIBUTES/VARIABLE_VALUE"))

    model = port(v)
    x = np.random.default_rng(0).random((1, 300, 84), dtype=np.float32) * 2
    with torch.no_grad():
        ours = model(torch.from_numpy(x)).numpy()
    err = float(np.abs(keras_reference(v, x) - ours).max())
    print(f"max |Keras - PyTorch| = {err:.1e}")
    assert err < 1e-4, err

    out = args.model_dir / ONNX_NAME
    torch.onnx.export(
        model,
        (torch.zeros(1, 500, 84),),
        str(out),
        input_names=["x"],
        output_names=["y"],
        dynamic_axes={"x": {1: "frames"}, "y": {1: "frames"}},
        opset_version=17,
        dynamo=False,
    )
    session = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
    err = float(np.abs(session.run(None, {"x": x})[0] - ours).max())
    print(f"max |ONNX Runtime - PyTorch| = {err:.1e}")
    assert err < 1e-4, err
    print(f"wrote {out}\nSHA-256 {hashlib.sha256(out.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
