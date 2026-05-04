"""Audio processing modules for Reachy Mini OpenClaw."""

from typing import Final

import numpy as np
from numpy.typing import NDArray
from scipy.signal import resample

from reachy_mini_openclaw.audio.head_wobbler import HeadWobbler

PCM16_MAX: Final[float] = 32767.0
PCM16_MIN_SCALE: Final[float] = 32768.0

__all__ = [
    "HeadWobbler",
    "pcm16_bytes",
    "pcm16_frame",
    "playback_audio_frame",
    "resample_audio",
    "to_mono_float32",
]


def to_mono_float32(audio: NDArray) -> NDArray[np.float32]:
    """Convert an audio frame to mono float32 samples in the -1..1 range."""
    if audio.ndim == 2:
        if audio.shape[1] > audio.shape[0]:
            audio = audio.T
        if audio.shape[1] > 1:
            audio = audio[:, 0]

    audio = audio.flatten()

    if audio.dtype == np.int16:
        return (audio.astype(np.float32) / PCM16_MIN_SCALE).astype(np.float32)
    if audio.dtype != np.float32:
        return audio.astype(np.float32)
    return audio


def resample_audio(audio: NDArray[np.float32], input_sample_rate: int, output_sample_rate: int) -> NDArray[np.float32]:
    """Resample mono float32 audio when the source and target rates differ."""
    if input_sample_rate == output_sample_rate or len(audio) == 0:
        return audio

    num_samples = int(len(audio) * output_sample_rate / input_sample_rate)
    return resample(audio, num_samples).astype(np.float32)


def pcm16_bytes(audio: NDArray, input_sample_rate: int, output_sample_rate: int) -> bytes:
    """Convert an audio frame to mono PCM16 bytes at the requested sample rate."""
    mono = to_mono_float32(audio)
    sampled = resample_audio(mono, input_sample_rate, output_sample_rate)
    clipped = np.clip(sampled, -1.0, 1.0)
    return (clipped * PCM16_MAX).astype(np.int16).tobytes()


def pcm16_frame(data: bytes) -> NDArray[np.int16]:
    """Convert raw PCM16 bytes to the frame shape expected by FastRTC."""
    return np.frombuffer(data, dtype=np.int16).reshape(1, -1)


def playback_audio_frame(
    audio: NDArray[np.int16],
    input_sample_rate: int,
    output_sample_rate: int,
    volume: float = 0.5,
) -> NDArray[np.float32]:
    """Convert provider PCM16 output to float32 robot playback samples."""
    samples = audio.flatten().astype(np.float32) / PCM16_MIN_SCALE
    if samples.size == 0:
        return samples

    samples = samples * volume
    if input_sample_rate == output_sample_rate:
        return samples.astype(np.float32)

    sample_count = max(1, round(len(samples) * output_sample_rate / input_sample_rate))
    return resample(samples, sample_count).astype(np.float32)
