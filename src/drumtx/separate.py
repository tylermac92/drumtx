"""Optional drum isolation with Open-Unmix `umxl` (decision 0003; M2-6).

Needs the `[separation]` extra (PyTorch, openunmix, safetensors), imported only when --separate
is used. The weights are loaded from safetensors (drumtx.models); the drum stem replaces the mix
for detection only. Beat tracking stays on the full mix (Technical Design Document §7).
"""

from typing import Literal

import numpy as np

from drumtx import models
from drumtx.errors import MissingDependencyError, install_hint
from drumtx.ingest import AudioBuffer

Device = Literal["cpu", "cuda"]
SEPARATOR = "umxl-drums"


def check_installed() -> None:
    try:
        import openunmix  # noqa: F401
        import safetensors  # noqa: F401
        import torch  # noqa: F401
    except ImportError as e:
        raise MissingDependencyError(
            f"--separate needs the separation extra ({e.name} is missing). Install it with:\n"
            f"  {install_hint('separation')}"
        ) from e


def isolate_drums(audio: AudioBuffer, offline: bool, device: Device) -> AudioBuffer:
    """The drum stem of `audio`, as mono at the same rate and length."""
    check_installed()  # before a 113 MB download that needs PyTorch to convert
    import torch
    from openunmix.model import OpenUnmix, Separator
    from openunmix.utils import bandwidth_to_max_bin
    from safetensors.torch import load_file

    if device == "cuda" and not torch.cuda.is_available():
        raise MissingDependencyError(
            "--device cuda: PyTorch sees no CUDA GPU. Install a CUDA build of PyTorch "
            "(https://pytorch.org/get-started/locally/) or use --device cpu."
        )
    weights = models.get_model(SEPARATOR, offline)
    # umxl's settings (openunmix.umxl): stereo, 4096-point STFT, 16 kHz bandwidth, one EM step.
    unmix = OpenUnmix(
        nb_bins=4096 // 2 + 1,
        nb_channels=2,
        hidden_size=1024,
        max_bin=bandwidth_to_max_bin(rate=44100.0, n_fft=4096, bandwidth=16000),
    )
    unmix.load_state_dict(load_file(str(weights)))
    separator = Separator(
        {"drums": unmix.eval()}, niter=1, residual=True, n_fft=4096, n_hop=1024, nb_channels=2
    ).to(device)
    x = audio.samples
    stereo = np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]
    with torch.no_grad():
        out = separator(torch.from_numpy(np.ascontiguousarray(stereo.T))[None].to(device))
    drums = out[0, 0].mean(dim=0).cpu().numpy().astype(np.float32)  # targets: drums, residual
    return AudioBuffer(drums[:, None], audio.start_s, audio.source_duration_s)
