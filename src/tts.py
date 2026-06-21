import asyncio
from pathlib import Path

import edge_tts

VOICES: dict[str, str] = {
    "Hindi": "hi-IN-SwaraNeural",
    "English": "en-IN-NeerjaNeural",
}


async def _synthesize(text: str, voice: str, output_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def speak_to_file(
    text: str,
    language: str = "Hindi",
    output_path: str | Path = "output.mp3",
) -> Path:
    """Convert text to speech, save as mp3. Returns the output Path."""
    voice = VOICES.get(language, VOICES["Hindi"])
    output_path = Path(output_path)
    asyncio.run(_synthesize(text, voice, output_path))
    return output_path


def speak(text: str, language: str = "Hindi", output_file: str | Path = "output.mp3") -> Path:
    """Backward-compatible alias used by app.py."""
    return speak_to_file(text, language, output_file)
