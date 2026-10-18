"""ChromaDB primary store for Echo chat messages, with a local embedding path."""
import asyncio
import json
import logging

from app.core.config import get_settings
from app.services.vector import local_embed

log = logging.getLogger("echocare.chat_store")
_collection = None


def _col():
    global _collection
    if _collection is None:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=get_settings().CHROMA_DIR,
                                          settings=Settings(anonymized_telemetry=False))
        _collection = client.get_or_create_collection(
            "echocare_chat_messages", embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}})
    return _collection


def _save_sync(row: dict):
    content = row["content"]
    metadata = {k: str(row.get(k) or "") for k in ("user_id", "profile_id", "role", "kind", "created_at")}
    metadata["payload"] = json.dumps({k: row.get(k) for k in ("tools_used", "web_sources", "is_emergency")},
                                     ensure_ascii=False)
    _col().upsert(ids=[row["_id"]], embeddings=local_embed([content]), documents=[content], metadatas=[metadata])


def _history_sync(profile_id: str, limit: int):
    rows = _col().get(where={"profile_id": profile_id}, include=["documents", "metadatas"])
    result = []
    for msg_id, content, metadata in zip(rows["ids"], rows["documents"], rows["metadatas"]):
        try:
            payload = json.loads(metadata.get("payload", "{}"))
        except (TypeError, ValueError):
            payload = {}
        result.append({"_id": msg_id, "user_id": metadata.get("user_id"), "profile_id": profile_id,
                       "role": metadata.get("role", "assistant"), "content": content,
                       "kind": metadata.get("kind") or None, "created_at": metadata.get("created_at", ""),
                       **payload})
    result.sort(key=lambda row: (row["created_at"], row["_id"]))
    return result[-limit:]


def _search_sync(profile_id: str, query: str, limit: int):
    col = _col()
    if col.count() == 0:
        return []
    result = col.query(query_embeddings=local_embed([query]), n_results=limit,
                       where={"profile_id": profile_id}, include=["documents", "metadatas", "distances"])
    return [{"role": m.get("role", "assistant"), "content": doc, "kind": m.get("kind") or None,
             "created_at": m.get("created_at", ""), "similarity": max(0.0, 1.0 - dist)}
            for doc, m, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0])]


def _clear_sync(profile_id: str):
    _col().delete(where={"profile_id": profile_id})


async def save(row: dict):
    await asyncio.to_thread(_save_sync, row)


async def history(profile_id: str, limit: int = 1000):
    return await asyncio.to_thread(_history_sync, profile_id, limit)


async def search(profile_id: str, query: str, limit: int = 5):
    return await asyncio.to_thread(_search_sync, profile_id, query, limit)


async def clear(profile_id: str):
    await asyncio.to_thread(_clear_sync, profile_id)
