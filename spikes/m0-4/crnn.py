"""CRNN used by the ADTOF Frame_RNN model, in PyTorch: port of its weights, ONNX export, inference.

python crnn.py convert   # TF checkpoint -> PyTorch, check against Keras, export ONNX
"""

import sys

import numpy as np
import torch
from common import DATA
from torch import nn

ADTOF_ORDER = ("kick", "snare", "tom", "hihat", "cymbal")  # ADTOF LABELS_5: 35, 38, 47, 42, 49
ADTOF_CKPT = DATA / "models" / "adtof" / "Frame_RNN_adtofAll_0"
ADTOF_ONNX = DATA / "models" / "adtof" / "frame_rnn_adtof_all_0.onnx"
ADTOF_THRESHOLDS = (0.22, 0.24, 0.32, 0.22, 0.30)  # from ADTOF hyperparameters, in ADTOF_ORDER


class SamePool(nn.Module):
    """MaxPool (1, 3) with TensorFlow "same" padding, which splits padding before and after."""

    def __init__(self, bins: int) -> None:
        super().__init__()
        total = -(-bins // 3) * 3 - bins
        self.pad = (total // 2, total - total // 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return nn.functional.max_pool2d(nn.functional.pad(x, self.pad, value=-torch.inf), (1, 3))


class CRNN(nn.Module):
    def __init__(self, filters=(32, 64), gru=(60, 60, 60), n_bins=84, n_out=5) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        c, bins = 1, n_bins
        for f in filters:
            for c_in in (c, f):
                layers += [nn.Conv2d(c_in, f, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(f, eps=1e-3)]
            layers += [SamePool(bins), nn.Dropout(0.3)]
            c, bins = f, -(-bins // 3)
        self.cnn = nn.Sequential(*layers)
        sizes = [c * bins] + [2 * g for g in gru]
        self.grus = nn.ModuleList(
            nn.GRU(i, g, batch_first=True, bidirectional=True)
            for i, g in zip(sizes, gru, strict=False)
        )
        self.out = nn.Linear(2 * gru[-1], n_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (batch, frames, bins) -> probabilities
        x = self.cnn(x[:, None]).permute(0, 2, 3, 1).flatten(2)  # Keras flattens (freq, channel)
        for g in self.grus:
            x, _ = g(x)
        return torch.sigmoid(self.out(x))


def _keras_gru_to_torch(w: np.ndarray) -> torch.Tensor:
    """Keras gate order (z, r, h) on the last axis -> PyTorch (r, z, n) on the first."""
    z, r, h = np.split(w, 3, axis=-1)
    return torch.from_numpy(np.concatenate([r, z, h], axis=-1).T.copy())


def convert() -> CRNN:
    import tensorflow as tf

    ckpt = tf.train.load_checkpoint(str(ADTOF_CKPT))

    def v(name: str) -> np.ndarray:
        return np.asarray(ckpt.get_tensor(name + "/.ATTRIBUTES/VARIABLE_VALUE"))

    model = CRNN().eval()
    convs = [m for m in model.cnn if isinstance(m, nn.Conv2d)]
    norms = [m for m in model.cnn if isinstance(m, nn.BatchNorm2d)]
    sd: dict[str, torch.Tensor] = {}
    for i, (conv, bn) in enumerate(zip(convs, norms, strict=True)):
        p = f"layer_with_weights-0/layer_with_weights-{2 * i}"
        q = f"layer_with_weights-0/layer_with_weights-{2 * i + 1}"
        conv.weight.data = torch.from_numpy(v(p + "/kernel").transpose(3, 2, 0, 1).copy())
        conv.bias.data = torch.from_numpy(v(p + "/bias"))
        bn.weight.data, bn.bias.data = (
            torch.from_numpy(v(q + "/gamma")),
            torch.from_numpy(v(q + "/beta")),
        )
        bn.running_mean.data = torch.from_numpy(v(q + "/moving_mean"))
        bn.running_var.data = torch.from_numpy(v(q + "/moving_variance"))
    for i, g in enumerate(model.grus):
        for keras_dir, suffix in (("forward_layer", ""), ("backward_layer", "_reverse")):
            p = f"layer_with_weights-{i + 1}/{keras_dir}/cell"
            b = v(p + "/bias")
            sd = {
                f"weight_ih_l0{suffix}": _keras_gru_to_torch(v(p + "/kernel")),
                f"weight_hh_l0{suffix}": _keras_gru_to_torch(v(p + "/recurrent_kernel")),
                f"bias_ih_l0{suffix}": _keras_gru_to_torch(b[0]),
                f"bias_hh_l0{suffix}": _keras_gru_to_torch(b[1]),
            }
            for k, t in sd.items():
                getattr(g, k).data = t
    model.out.weight.data = torch.from_numpy(v("layer_with_weights-4/kernel").T.copy())
    model.out.bias.data = torch.from_numpy(v("layer_with_weights-4/bias"))
    _check_against_keras(model, v)
    return model


def _check_against_keras(model: CRNN, v) -> None:  # type: ignore[no-untyped-def]
    """Rebuild the network in Keras with the same weights; outputs must match the port."""
    from tensorflow import keras

    inp = keras.Input((None, 84, 1))
    x, weights = inp, []
    for i, f in enumerate((32, 64)):
        for j in range(2):
            p = f"layer_with_weights-0/layer_with_weights-{4 * i + 2 * j}"
            q = f"layer_with_weights-0/layer_with_weights-{4 * i + 2 * j + 1}"
            conv = keras.layers.Conv2D(f, 3, padding="same", activation="relu")
            bn = keras.layers.BatchNormalization()
            x = bn(conv(x))
            weights += [
                (conv, [v(p + "/kernel"), v(p + "/bias")]),
                (bn, [v(q + n) for n in ("/gamma", "/beta", "/moving_mean", "/moving_variance")]),
            ]
        x = keras.layers.MaxPool2D((1, 3), padding="same")(x)
    x = keras.layers.Reshape((-1, 640))(x)
    for i in range(3):
        layer = keras.layers.Bidirectional(keras.layers.GRU(60, return_sequences=True))
        x = layer(x)
        ws = []
        for d in ("forward_layer", "backward_layer"):
            p = f"layer_with_weights-{i + 1}/{d}/cell"
            ws += [v(p + "/kernel"), v(p + "/recurrent_kernel"), v(p + "/bias")]
        weights.append((layer, ws))
    dense = keras.layers.Dense(5, activation="sigmoid")
    out = dense(x)
    weights.append((dense, [v("layer_with_weights-4/kernel"), v("layer_with_weights-4/bias")]))
    keras_model = keras.Model(inp, out)
    for layer, ws in weights:
        layer.set_weights(ws)
    x = np.random.default_rng(0).random((1, 300, 84), dtype=np.float32) * 2
    want = keras_model.predict(x[..., None], verbose=0)
    with torch.no_grad():
        got = model(torch.from_numpy(x)).numpy()
    err = float(np.abs(want - got).max())
    print(f"max |keras - torch| = {err:.2e}")
    assert err < 1e-4, err


def export_onnx(model: CRNN, path) -> None:  # type: ignore[no-untyped-def]
    torch.onnx.export(
        model.eval(),
        (torch.zeros(1, 500, 84),),
        str(path),
        input_names=["x"],
        output_names=["y"],
        dynamic_axes={"x": {1: "frames"}, "y": {1: "frames"}},
        opset_version=17,
        dynamo=False,
    )


if __name__ == "__main__" and sys.argv[1:] == ["convert"]:
    export_onnx(convert(), ADTOF_ONNX)
    print("wrote", ADTOF_ONNX, ADTOF_ONNX.stat().st_size, "bytes")
