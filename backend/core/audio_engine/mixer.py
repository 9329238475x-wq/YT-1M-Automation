from __future__ import annotations

import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import butter, sosfilt


def _apply_binaural_3d_immersion(audio: np.ndarray, sr: int = 48000) -> np.ndarray:
    """Transforms audio into an expansive, mind-enveloping 3D earphone soundscape:
    1. Mid-Side 3D Widening: Sound wraps around the head instead of sitting inside the skull.
    2. Binaural Cross-Feed & Head-Shadow Delay: Creates true 3D spatial outdoor perception.
    3. Deep Sub-Bass Mind-Resonance (35 Hz - 140 Hz): Soothing low-frequency warmth that relaxes the brain.
    4. Anti-Fatigue Treble Shield: Softens harsh high frequencies above 8.5 kHz for hours of effortless listening.
    """
    left = audio[:, 0].copy()
    right = audio[:, 1].copy()

    # 1. Mid / Side 3D Widening (expands the soundstage all around the listener)
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    side_boosted = side * 1.45
    mid_calm = mid * 0.88

    left_w = mid_calm + side_boosted
    right_w = mid_calm - side_boosted

    # 2. Binaural cross-feed with head-shadow delay (0.35ms ~ 17 samples)
    delay_samples = max(int(sr * 0.00035), 1)
    sos_shadow = butter(1, 1800.0, btype="lowpass", fs=sr, output="sos")

    shadow_r_to_l = np.pad(right_w[:-delay_samples], (delay_samples, 0))
    shadow_r_to_l = sosfilt(sos_shadow, shadow_r_to_l) * 0.18

    shadow_l_to_r = np.pad(left_w[:-delay_samples], (delay_samples, 0))
    shadow_l_to_r = sosfilt(sos_shadow, shadow_l_to_r) * 0.18

    left_3d = left_w + shadow_r_to_l
    right_3d = right_w + shadow_l_to_r

    # 3. Deep sub-bass warmth (35 Hz - 140 Hz) for heavy, relaxing, full-body rumble
    sos_deep = butter(2, [35.0, 140.0], btype="bandpass", fs=sr, output="sos")
    sub_l = sosfilt(sos_deep, left_3d) * 0.45
    sub_r = sosfilt(sos_deep, right_3d) * 0.45
    left_3d += sub_l
    right_3d += sub_r

    # 4. Anti-fatigue treble shield (softens harsh highs above 8.5 kHz)
    sos_smooth = butter(1, 8500.0, btype="lowpass", fs=sr, output="sos")
    left_3d = left_3d * 0.75 + sosfilt(sos_smooth, left_3d) * 0.25
    right_3d = right_3d * 0.75 + sosfilt(sos_smooth, right_3d) * 0.25

    return np.stack([left_3d, right_3d], axis=1)


def mix_and_write(layers: dict[str, np.ndarray], output: str | Path, weights: dict[str, float]) -> Path:
    if not layers:
        raise ValueError("No audio layers supplied")
    length = min(len(x) for x in layers.values())
    mix = np.zeros((length, 2), dtype=np.float32)
    for name, audio in layers.items():
        weight = float(weights.get(name, 0.0))
        if weight > 0:
            mix += audio[:length] * weight

    # Apply 3D Binaural Immersion (wrap-around earphone experience)
    mix = _apply_binaural_3d_immersion(mix, sr=48000)

    # Soft analog tape warming saturation
    mix = np.tanh(mix * 1.05)

    # Master peak normalization (-1.4 dBFS = ~0.85) for rich, clear, deeply immersive playback
    peak = float(np.max(np.abs(mix)))
    if peak > 0:
        mix = (mix / peak) * 0.85

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, mix, 48000, subtype="PCM_16")
    return path
