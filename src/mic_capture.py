import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1


def record(duration: int = 7, output_path: str | Path = "input.wav") -> Path:
    """Record audio from the default microphone and save as WAV. Returns output Path."""
    output_path = Path(output_path)

    print(f"  Recording {duration}s — speak now...")
    audio: np.ndarray = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )
    sd.wait()
    print("  Recording done.")

    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    return output_path


def record_audio(duration: int = 7, output_file: str | Path = "input.wav") -> Path:
    """Backward-compatible alias used by app.py."""
    return record(duration, output_file)
