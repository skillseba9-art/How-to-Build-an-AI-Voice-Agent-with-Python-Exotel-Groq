import os
from pathlib import Path

from groq import Groq
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_client: Groq | None = None

# Normalize locale codes like "en-IN" → "en", "hi-IN" → "hi"
_LANG_MAP = {
    "en-in": "en", "en-us": "en", "en-gb": "en",
    "hi-in": "hi", "english": "en", "hindi": "hi",
}


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set in .env — "
                "get a free key at https://console.groq.com"
            )
        _client = Groq(api_key=api_key)
    return _client


def _normalize_lang(language: str) -> str | None:
    """Convert locale strings to ISO 639-1 codes GROQ Whisper accepts."""
    if not language or language.lower() == "auto":
        return None
    return _LANG_MAP.get(language.lower(), language.lower()[:2])


def transcribe(audio_path: str | Path, language: str = "hi") -> str:
    """
    Transcribe audio file using GROQ Whisper.
    language: 'hi'/'en' ISO code, locale like 'en-IN', or 'auto'.
    Returns transcribed text, or empty string on failure.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    lang_param = _normalize_lang(language)

    try:
        with open(audio_path, "rb") as f:
            result = _get_client().audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                language=lang_param,
                response_format="text",
            )
        text = result if isinstance(result, str) else result.text
        return text.strip()
    except Exception as exc:
        print(f"STT error: {exc}")
        return ""


# Backward-compatible alias used by app.py
def transcribe_audio(audio_file: str | Path, language: str = "hi") -> str:
    return transcribe(audio_file, language)
