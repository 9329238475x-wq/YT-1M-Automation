from __future__ import annotations

import numpy as np
import soundfile as sf
from pathlib import Path


def mix_and_write(layers: dict[str, np.ndarray], output: str | Path, weights: dict[str, float]) -> Path:
    if not layers:
        raise ValueError("No audio layers supplied")
    length = min(len(x) for x in layers.values())
    mix = np.zeros((length, 2), dtype=np.float32)
    for name, audio in layers.items():
        mix += audio[:length] * float(weights.get(name, 0.0))
    peak = float(np.max(np.abs(mix)))
    if peak > 0.98:
        mix *= 0.98 / peak
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, mix, 48000, subtype="PCM_16")
    return path
