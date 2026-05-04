import numpy as np

from reachy_mini_openclaw.audio import pcm16_bytes, pcm16_frame, resample_audio, to_mono_float32


def test_to_mono_float32_normalizes_int16_audio():
    audio = np.array([[0, 1000], [32767, -32768]], dtype=np.int16)

    mono = to_mono_float32(audio)

    assert mono.dtype == np.float32
    assert mono.shape == (2,)
    assert mono[0] == 0.0


def test_resample_audio_changes_frame_length():
    audio = np.linspace(-0.5, 0.5, 240, dtype=np.float32)

    sampled = resample_audio(audio, 24000, 16000)

    assert sampled.dtype == np.float32
    assert len(sampled) == 160


def test_resample_audio_keeps_empty_audio_empty():
    audio = np.array([], dtype=np.float32)

    sampled = resample_audio(audio, 24000, 16000)

    assert sampled.size == 0


def test_pcm16_bytes_resamples_to_target_rate():
    audio = np.linspace(-0.5, 0.5, 240, dtype=np.float32)

    data = pcm16_bytes(audio, 24000, 16000)

    assert len(data) == 160 * 2


def test_pcm16_frame_returns_fastrtc_shape():
    source = np.array([1, -1, 2, -2], dtype=np.int16)

    frame = pcm16_frame(source.tobytes())

    assert frame.dtype == np.int16
    assert frame.shape == (1, 4)
    assert frame.tolist() == [[1, -1, 2, -2]]
