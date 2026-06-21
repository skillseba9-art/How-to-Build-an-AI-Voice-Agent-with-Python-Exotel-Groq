import os
import ssl
from pathlib import Path
from typing import List

# Windows SSL certificate fix — must run BEFORE importing sentence_transformers
# huggingface_hub uses httpx which has its own SSL stack
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001

import httpx  # noqa: E402  (must be patched before sentence_transformers loads)

_orig_client = httpx.Client.__init__
_orig_async = httpx.AsyncClient.__init__


def _no_verify_client(self, *args, **kwargs):
    kwargs.setdefault("verify", False)
    _orig_client(self, *args, **kwargs)


def _no_verify_async(self, *args, **kwargs):
    kwargs.setdefault("verify", False)
    _orig_async(self, *args, **kwargs)


httpx.Client.__init__ = _no_verify_client
httpx.AsyncClient.__init__ = _no_verify_async

from sentence_transformers import SentenceTransformer  # noqa: E402
import chromadb  # noqa: E402

KB_PATH = Path(__file__).parent.parent / "knowledge_base" / "school_info.txt"

_model: SentenceTransformer | None = None
_collection = None
_client = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("Loading embedding model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_collection():
    global _collection, _client
    if _collection is not None:
        return _collection
    _client = chromadb.Client()
    _collection = _client.get_or_create_collection(
        "school_kb",
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def _load_chunks(filepath: Path) -> List[str]:
    text = filepath.read_text(encoding="utf-8")
    chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 40]
    return chunks


def build_index() -> None:
    collection = _get_collection()
    if collection.count() > 0:
        print(f"KB index already loaded: {collection.count()} chunks")
        return

    if not KB_PATH.exists():
        raise FileNotFoundError(f"Knowledge base not found: {KB_PATH}")

    chunks = _load_chunks(KB_PATH)
    model = _get_model()
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[f"chunk_{i}" for i in range(len(chunks))],
    )
    print(f"KB index built: {len(chunks)} chunks indexed")


def query_kb(question: str, top_k: int = 3) -> str:
    """Return relevant context from the knowledge base for a given question."""
    collection = _get_collection()
    if collection.count() == 0:
        build_index()

    model = _get_model()
    q_embed = model.encode([question], show_progress_bar=False).tolist()
    results = collection.query(
        query_embeddings=q_embed,
        n_results=top_k,
        include=["documents", "distances"],
    )

    docs = results["documents"][0]
    distances = results["distances"][0]

    # cosine distance < 0.6 considered relevant
    relevant = [doc for doc, dist in zip(docs, distances) if dist < 0.6]
    return "\n\n".join(relevant) if relevant else ""


# Backward-compatible alias used by app.py
index_knowledge_base = build_index
