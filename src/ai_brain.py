import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from rag_pipeline import build_index, query_kb

load_dotenv(Path(__file__).parent.parent / ".env")

_client = None
_provider: str = ""   # "groq" or "openrouter"

SYSTEM_PROMPT = """You are an AI admission counselor for Modern Academy, a premier CBSE school in Delhi, India.

STRICT RULES:
1. Answer ONLY using the SCHOOL CONTEXT provided below — never make up data.
2. If the context does not contain the answer, say:
   Hindi: "Iske liye main aapko hamare counselor se connect karta hoon."
   English: "For this, let me connect you with our admission counselor."
3. Keep every reply SHORT — 2 to 3 sentences maximum.
4. Be warm, friendly, and persuasive.
5. Always try to move the conversation toward scheduling a school visit or a callback.
6. Speak in {language} only.

SCHOOL CONTEXT:
{context}"""

NO_CONTEXT_REPLY = {
    "Hindi": "Iske liye main aapko hamare counselor se connect karta hoon.",
    "English": "For this, let me connect you with our admission counselor.",
}

ERROR_REPLY = {
    "Hindi": "Kshama karen, abhi thodi technical samasya hai. Kripaya thodi der baad try karein.",
    "English": "Sorry, there is a brief technical issue. Please try again in a moment.",
}


def _get_client():
    """
    Return an LLM client. Priority:
      1. GROQ (groq SDK)  — if GROQ_API_KEY is set
      2. OpenRouter (openai-compatible)  — if Open_Router_API_KEY is set
    Raises EnvironmentError if neither key is found.
    """
    global _client, _provider
    if _client is not None:
        return _client

    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("Open_Router_API_KEY")

    if groq_key:
        from groq import Groq
        _client = Groq(api_key=groq_key)
        _provider = "groq"
        print("LLM provider: GROQ")
    elif openrouter_key:
        from openai import OpenAI
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
        )
        _provider = "openrouter"
        print("LLM provider: OpenRouter")
    else:
        raise EnvironmentError(
            "No LLM API key found. Set GROQ_API_KEY or Open_Router_API_KEY in .env"
        )

    return _client


def initialize() -> None:
    """Pre-load embedding model and build ChromaDB index."""
    build_index()


def get_ai_response(
    user_message: str,
    language: str = "Hindi",
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    if chat_history is None:
        chat_history = []

    context = query_kb(user_message)
    if not context:
        return NO_CONTEXT_REPLY.get(language, NO_CONTEXT_REPLY["Hindi"])

    system_content = SYSTEM_PROMPT.format(language=language, context=context)

    messages = (
        [{"role": "system", "content": system_content}]
        + chat_history
        + [{"role": "user", "content": user_message}]
    )

    # Ensure client is initialized so _provider is set before model selection
    _get_client()

    # Model selection per provider
    if _provider == "groq":
        models = ["llama-3.3-70b-versatile"]
    else:
        # OpenRouter free models — verified available, try in order
        models = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "deepseek/deepseek-v4-flash:free",
            "google/gemma-4-31b-it:free",
            "openai/gpt-oss-20b:free",
            "meta-llama/llama-3.2-3b-instruct:free",
        ]

    import time

    for model in models:
        try:
            response = _get_client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str:
                import re
                match = re.search(r"retry_after_seconds.*?(\d+)", err_str)
                wait = int(match.group(1)) if match else 30
                print(f"Rate limited on {model}, waiting {wait}s -> trying next...")
                time.sleep(min(wait, 35))
            else:
                print(f"LLM error ({model}): {exc}")
            continue

    return ERROR_REPLY.get(language, ERROR_REPLY["Hindi"])
