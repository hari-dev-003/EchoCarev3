"""ChromaDB vector store for LE-RAG.

Design:
  * MongoDB is the source of truth for evidence chunks; Chroma is a re-buildable semantic index.
  * We ALWAYS pass explicit embeddings (never Chroma's default ONNX model, which needs a download).
  * 384-dim vectors: Gemini embeddings (output_dimensionality=384, normalised) when configured,
    else a deterministic local hashing embedding. One collection per backend so spaces never mix.
  * Per-profile isolation through the `profile_id` metadata filter.
"""
import asyncio
import logging
import re
import threading

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from app.core.config import get_settings
from app.services import llm

log = logging.getLogger("echocare.vector")
_lock = threading.Lock()
_client = None

_hasher = HashingVectorizer(n_features=384, alternate_sign=False, norm="l2", ngram_range=(1, 2),
                            stop_words="english", analyzer="word", lowercase=True)
_char_hasher = HashingVectorizer(n_features=384, alternate_sign=False, norm="l2", analyzer="char_wb", ngram_range=(3, 5))


def local_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic offline embedding: word n-grams blended with char n-grams (typo / morphology tolerant)."""
    w = _hasher.transform(texts).toarray()
    c = _char_hasher.transform(texts).toarray()
    m = 0.6 * w + 0.4 * c
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return (m / n).tolist()


async def embed(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> tuple[list[list[float]], str]:
    """Returns (vectors, backend) where backend is 'gemini' or 'local'."""
    if llm.gemini_configured():
        vecs = await llm.embed_gemini(texts, task)
        if vecs:
            return vecs, "gemini"
    return await asyncio.to_thread(local_embed, texts), "local"


def _get_client():
    global _client
    with _lock:
        if _client is None:
            import chromadb
            from chromadb.config import Settings as CS
            _client = chromadb.PersistentClient(path=get_settings().CHROMA_DIR, settings=CS(anonymized_telemetry=False))
        return _client


def _collection(backend: str):
    return _get_client().get_or_create_collection(
        name=f"echocare_evidence_{backend}", embedding_function=None,
        configuration={"hnsw": {"space": "cosine"}})


def _upsert_sync(backend, ids, vectors, docs, metas):
    _collection(backend).upsert(ids=ids, embeddings=vectors, documents=docs, metadatas=metas)


def _query_sync(backend, vector, profile_id, n, source_type=None):
    where = {"profile_id": profile_id} if not source_type else {"$and": [{"profile_id": profile_id}, {"source_type": source_type}]}
    col = _collection(backend)
    r = col.query(query_embeddings=[vector], n_results=max(1, n), where=where)
    ids, dists = r["ids"][0], r["distances"][0]
    return [(i, max(0.0, 1.0 - d)) for i, d in zip(ids, dists)]  # cosine distance -> similarity


def _delete_sync(profile_id=None, ids=None):
    for backend in ("gemini", "local"):
        try:
            col = _collection(backend)
            if ids:
                col.delete(ids=ids)
            elif profile_id:
                col.delete(where={"profile_id": profile_id})
        except Exception as e:
            log.warning("chroma delete failed (%s): %s", backend, e)


def _count_sync() -> dict:
    out = {}
    for backend in ("gemini", "local"):
        try:
            out[backend] = _collection(backend).count()
        except Exception:
            out[backend] = 0
    return out


async def upsert(profile_id: str, chunks: list[dict]) -> str:
    """chunks: [{id, text, source_type, themes, timestamp}] -> backend used."""
    if not chunks:
        return "local"
    vecs, backend = await embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
    metas = [{"profile_id": profile_id, "source_type": c["source_type"], "themes": ",".join(c["themes"]),
              "timestamp": c["timestamp"]} for c in chunks]
    await asyncio.to_thread(_upsert_sync, backend, [c["id"] for c in chunks], vecs, [c["text"] for c in chunks], metas)
    return backend


async def query(profile_id: str, text: str, n: int = 6, source_type: str | None = None) -> tuple[list[tuple[str, float]], str]:
    vecs, backend = await embed([text], "RETRIEVAL_QUERY")
    hits = await asyncio.to_thread(_query_sync, backend, vecs[0], profile_id, n, source_type)
    return hits, backend


def _query_docs_sync(backend, vector, profile_id, n, source_type=None):
    where = {"profile_id": profile_id} if not source_type else {"$and": [{"profile_id": profile_id}, {"source_type": source_type}]}
    r = _collection(backend).query(query_embeddings=[vector], n_results=max(1, n), where=where,
                                    include=["documents", "metadatas", "distances"])
    rows = []
    for doc_id, doc, meta, distance in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]):
        rows.append(({"_id": doc_id, "profile_id": profile_id, "source_type": meta.get("source_type", "unknown"),
                      "text": doc, "theme_tags": [t for t in meta.get("themes", "").split(",") if t],
                      "timestamp": meta.get("timestamp", "")}, max(0.0, 1.0 - distance)))
    return rows


async def query_docs(profile_id: str, text: str, n: int = 6, source_type: str | None = None):
    """Retrieve evidence documents directly from Chroma without consulting MongoDB."""
    vecs, backend = await embed([text], "RETRIEVAL_QUERY")
    rows = await asyncio.to_thread(_query_docs_sync, backend, vecs[0], profile_id, n, source_type)
    return rows, backend


async def delete_profile(profile_id: str):
    await asyncio.to_thread(_delete_sync, profile_id, None)


async def delete_ids(ids: list[str]):
    if ids:
        await asyncio.to_thread(_delete_sync, None, ids)


async def stats() -> dict:
    counts = await asyncio.to_thread(_count_sync)
    return {"collections": counts, "persist_dir": get_settings().CHROMA_DIR,
            "active_embedding_backend": "gemini" if llm.gemini_configured() else "local"}
