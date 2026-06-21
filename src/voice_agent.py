"""
Main voice agent loop.

Usage:
  python voice_agent.py              # interactive demo (uses microphone)
  python voice_agent.py +91XXXXXXXXXX   # with phone number for CRM logging
  python voice_agent.py --text       # text-only mode (no mic, for quick testing)
"""

import sys
import io
import subprocess
from pathlib import Path

# Windows console UTF-8 fix — prevents UnicodeEncodeError for Hindi/special chars
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# make local modules importable
sys.path.insert(0, str(Path(__file__).parent))

from mic_capture import record
from stt import transcribe
from ai_brain import get_ai_response, initialize
from tts import speak_to_file
from crm_updater import push_to_crm

import os, requests as _req, urllib3 as _u3
_u3.disable_warnings()
_N8N_FOLLOWUP = os.getenv("N8N_FOLLOWUP_WEBHOOK", "")

ROOT = Path(__file__).parent.parent
TMP_INPUT = ROOT / "tmp_input.wav"
TMP_OUTPUT = ROOT / "tmp_output.mp3"

MAX_TURNS = 12

EXIT_PHRASES = [
    "nahi chahiye", "rehne do", "not interested", "no thanks",
    "band karo", "mat karo", "goodbye", "bye bye",
]

HIGHLY_INTERESTED_PHRASES = [
    "visit", "aana chahta", "aana chahti", "school dekhna",
    "admission karana", "admission chahiye", "when can we come",
]

INTERESTED_PHRASES = [
    "haan", "yes", "batao", "interested", "bataiye", "theek hai",
    "okay", "tell me", "details do",
]

BUSY_PHRASES = [
    "busy", "baad mein", "baad main", "call back", "call later",
    "abhi nahi", "thoda time",
]


def _play(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.run(["start", "/wait", "", str(path)], shell=True)
    elif sys.platform == "darwin":
        subprocess.run(["afplay", str(path)])
    else:
        subprocess.run(["mpg123", "-q", str(path)])


def _detect_language(text: str) -> str | None:
    t = text.lower()
    if any(w in t for w in ["english", "in english", "english mein", "english me"]):
        return "English"
    if any(w in t for w in ["hindi", "hindi mein", "hindi me"]):
        return "Hindi"
    return None


def _detect_outcome(text: str) -> str | None:
    t = text.lower()
    if any(p in t for p in HIGHLY_INTERESTED_PHRASES):
        return "highly_interested"
    if any(p in t for p in INTERESTED_PHRASES):
        return "interested"
    if any(p in t for p in BUSY_PHRASES):
        return "busy"
    if any(p in t for p in EXIT_PHRASES):
        return "not_interested"
    return None


def run_agent(phone: str = "demo", text_mode: bool = False) -> None:
    print("\n=== Modern Academy AI Admission Agent ===")
    print("Loading knowledge base...")
    initialize()

    language = "Hindi"
    chat_history: list[dict] = []
    call_outcome = "no_answer"
    summary_parts: list[str] = []

    greeting = (
        "Namaste! Main Modern Academy ka AI admission assistant hoon. "
        "Aapka bahut swagat hai. "
        "Kya aap Hindi mein baat karna chahenge ya English mein?"
    )
    print(f"\nAgent: {greeting}\n")
    audio = speak_to_file(greeting, "Hindi", TMP_OUTPUT)
    _play(audio)

    for turn in range(MAX_TURNS):
        try:
            prompt = "[text] Type message: " if text_mode else "Press Enter to speak (q=quit, t:<msg> for text): "
            cmd = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if cmd.lower() == "q":
            break

        # text shortcut for testing
        if text_mode or cmd.startswith("t:"):
            user_text = cmd[2:].strip() if cmd.startswith("t:") else cmd
        else:
            audio_file = record(duration=7, output_path=TMP_INPUT)
            user_text = transcribe(audio_file, language="hi" if language == "Hindi" else "en")

        if not user_text:
            print("Could not hear clearly. Please try again.")
            continue

        print(f"You: {user_text}")

        # Language switch
        switched = _detect_language(user_text)
        if switched and switched != language:
            language = switched
            print(f"[Switched to {language}]")

        # Outcome detection
        detected = _detect_outcome(user_text)
        if detected:
            call_outcome = detected

        # Early exit if clearly not interested
        if detected == "not_interested":
            farewell = (
                "Theek hai, koi baat nahi. Jab bhi zaroorat ho, hume call karein. Dhanyavaad!"
                if language == "Hindi"
                else "No problem at all. Feel free to call us anytime. Thank you!"
            )
            print(f"Agent: {farewell}\n")
            audio = speak_to_file(farewell, language, TMP_OUTPUT)
            _play(audio)
            break

        # Get AI response from RAG + LLM
        ai_text = get_ai_response(user_text, language, chat_history)
        print(f"Agent: {ai_text}\n")
        audio = speak_to_file(ai_text, language, TMP_OUTPUT)
        _play(audio)

        chat_history += [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": ai_text},
        ]
        summary_parts.append(f"User: {user_text[:80]} | Agent: {ai_text[:80]}")

    # Push result to CRM (Google Sheets direct)
    summary = " || ".join(summary_parts[-3:]) if summary_parts else "Call completed, no transcript."
    push_to_crm(
        phone=phone,
        call_outcome=call_outcome,
        ai_summary=summary,
        language=language,
    )

    # Notify n8n Follow-up Scheduler
    if _N8N_FOLLOWUP and phone != "demo":
        try:
            _req.post(
                _N8N_FOLLOWUP,
                json={"phone": phone, "outcome": call_outcome},
                timeout=5,
                verify=False,
            )
            print(f"  n8n follow-up scheduler notified")
        except Exception:
            pass  # non-critical

    print(f"\nCall ended. Outcome: {call_outcome}")

    for tmp in [TMP_INPUT, TMP_OUTPUT]:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    text_mode = "--text" in args
    phone_args = [a for a in args if a != "--text"]
    phone_number = phone_args[0] if phone_args else "demo"
    run_agent(phone=phone_number, text_mode=text_mode)
