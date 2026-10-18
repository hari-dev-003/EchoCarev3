"""Alg. 3: LE-RAG (Longitudinal Evidence RAG) on ChromaDB + MongoDB.

Mongo holds the evidence chunks (source of truth). Chroma holds their semantic index. Insight generation
passes an evidence-sufficiency gate (>=2 occurrences across >=2 distinct source types), retrieves the most
relevant chunks from Chroma, and scores confidence with an explainable composite."""
import re
from datetime import datetime

from app.core.db import get_db
from app.core.util import new_id, now_iso
from app.data.specialties import KEYWORD_TO_SPECIALTY, SPECIALTIES
from app.services import llm, vector

MIN_OCCURRENCES = 2
MIN_DISTINCT_SOURCES = 2
CONFIDENCE_THRESHOLD = 0.4
W = {"similarity": 0.4, "source_diversity": 0.25, "occurrence_rate": 0.2, "temporal_consistency": 0.15}

TIMELINE_PATTERN = re.compile(
    r"\b(for|since|over the (last|past))\s+(the\s+)?(\d+\s*(day|days|week|weeks|month|months|year|years)|"
    r"few\s+(days|weeks|months)|a\s+(day|week|month|year))\b", re.IGNORECASE)


def extract_timeline(text: str) -> str | None:
    m = TIMELINE_PATTERN.search(text)
    return m.group(0) if m else None


def tag_themes(text: str) -> list[str]:
    t = text.lower()
    return sorted({sp for kw, sp in KEYWORD_TO_SPECIALTY.items() if kw in t}) or ["general_wellbeing"]


def chunk_text(text: str, max_len: int = 260) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) <= max_len:
            buf = f"{buf} {s}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks or [text]


async def add_evidence(user_id: str, profile_id: str, source_type: str, text: str, metadata: dict | None = None) -> int:
    """Write evidence to Chroma first, then mirror it to MongoDB when available."""
    if not text or not text.strip():
        return 0
    docs = []
    ts = now_iso()
    for piece in chunk_text(text):
        docs.append({"_id": new_id(), "user_id": user_id, "profile_id": profile_id, "source_type": source_type,
                     "text": piece, "theme_tags": tag_themes(piece), "metadata": metadata or {},
                     "timestamp": ts, "indexed": False})
    backend = await vector.upsert(profile_id, [{"id": d["_id"], "text": d["text"], "source_type": d["source_type"],
                                                "themes": d["theme_tags"], "timestamp": d["timestamp"]} for d in docs])
    for d in docs:
        d["indexed"] = True
        d["index_backend"] = backend
    try:
        await get_db().evidence_chunks.insert_many(docs)
    except Exception as e:
        import logging
        logging.getLogger("echocare.rag").warning("Evidence stored in ChromaDB; MongoDB mirror failed: %s", e)
    return len(docs)


async def index_chunks(profile_id: str, docs: list[dict]) -> bool:
    try:
        backend = await vector.upsert(profile_id, [{"id": d["_id"], "text": d["text"], "source_type": d["source_type"],
                                                    "themes": d["theme_tags"], "timestamp": d["timestamp"]} for d in docs])
        await get_db().evidence_chunks.update_many({"_id": {"$in": [d["_id"] for d in docs]}},
                                                   {"$set": {"indexed": True, "index_backend": backend}})
        return True
    except Exception:  # Chroma problems must never lose the user's data: Mongo already has it; reindex later
        return False


async def reindex_all(profile_id: str | None = None) -> dict:
    """Rebuilds the Chroma index from MongoDB (admin tool; also self-heals after switching embedding backend)."""
    db = get_db()
    q = {"profile_id": profile_id} if profile_id else {}
    docs = await db.evidence_chunks.find(q).to_list(100000)
    by_profile: dict[str, list] = {}
    for d in docs:
        by_profile.setdefault(d["profile_id"], []).append(d)
    n = 0
    for pid, items in by_profile.items():
        for i in range(0, len(items), 64):
            if await index_chunks(pid, items[i:i + 64]):
                n += len(items[i:i + 64])
    return {"profiles": len(by_profile), "chunks_indexed": n, "chunks_total": len(docs)}


async def delete_for_profile(profile_id: str):
    await get_db().evidence_chunks.delete_many({"profile_id": profile_id})
    await vector.delete_profile(profile_id)


async def search(profile_id: str, query: str, top_k: int = 6, source_type: str | None = None) -> tuple[list[tuple[dict, float]], str]:
    """Semantic search in Chroma; falls back to TF-IDF over Mongo chunks if Chroma is unavailable."""
    db = get_db()
    try:
        hits, backend = await vector.query(profile_id, query, top_k, source_type)
        if hits:
            ids = [h[0] for h in hits]
            docs = {d["_id"]: d for d in await db.evidence_chunks.find({"_id": {"$in": ids}}).to_list(len(ids))}
            res = [(docs[i], s) for i, s in hits if i in docs]
            if res:
                return res, f"chromadb ({backend} embeddings)"
    except Exception:
        pass
    q = {"profile_id": profile_id, **({"source_type": source_type} if source_type else {})}
    chunks = await db.evidence_chunks.find(q).to_list(5000)
    return _tfidf(chunks, query, top_k), "keyword (TF-IDF fallback)"


async def search_chroma(profile_id: str, query: str, top_k: int = 6, source_type: str | None = None):
    """Chat retrieval path: return Chroma documents directly, with no MongoDB lookup."""
    try:
        hits, backend = await vector.query_docs(profile_id, query, top_k, source_type)
        return hits, f"chromadb ({backend} embeddings)"
    except Exception as e:
        import logging
        logging.getLogger("echocare.rag").warning("Chroma retrieval failed: %s", e)
        return [], "chromadb unavailable"


def _tfidf(chunks, query, top_k):
    if not chunks:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    try:
        m = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform([c["text"] for c in chunks] + [query])
    except ValueError:
        return []
    sims = cosine_similarity(m[-1], m[:-1])[0]
    order = sorted(range(len(chunks)), key=lambda i: -sims[i])[:top_k]
    return [(chunks[i], float(sims[i])) for i in order]


def composite_confidence(sims, source_types, occurrence_count, span_days):
    if not sims:
        return 0.0, {}
    parts = {
        "similarity": max(0.0, min(sum(sims) / len(sims), 1.0)),
        "source_diversity": min(len(source_types) / 4, 1.0),
        "occurrence_rate": min(occurrence_count / 8, 1.0),
        "temporal_consistency": min(span_days / 21, 1.0) if span_days else 0.25,
    }
    score = sum(W[k] * parts[k] for k in W)
    return round(min(score, 1.0), 3), {k: round(v, 3) for k, v in parts.items()}


def confidence_label(score: float) -> str:
    return "high" if score >= 0.65 else "moderate" if score >= CONFIDENCE_THRESHOLD else "low"


async def generate_insights(user_id: str, profile_id: str, lang: str = "en") -> list[dict]:
    db = get_db()
    chunks = await db.evidence_chunks.find({"profile_id": profile_id}).to_list(10000)
    themes: dict[str, list] = {}
    for c in chunks:
        for t in c["theme_tags"]:
            themes.setdefault(t, []).append(c)
    insights = []
    for theme, tchunks in themes.items():
        if theme == "general_wellbeing":
            continue
        sources = {c["source_type"] for c in tchunks}
        if len(tchunks) < MIN_OCCURRENCES or len(sources) < MIN_DISTINCT_SOURCES:
            continue  # evidence-sufficiency gate: never bypassed
        query = f"{theme}: " + ", ".join(SPECIALTIES.get(theme, [])[:6])
        hits, method = await search(profile_id, query, 6)
        # restrict retrieved evidence to this theme so one theme's insight never cites another's chunks
        hits = [(c, s) for c, s in hits if theme in c["theme_tags"]] or [(c, 0.0) for c in tchunks[:6]]
        retrieved = [c for c, _ in hits]
        sims = [max(s, 0.0) for _, s in hits]
        stamps = [datetime.fromisoformat(c["timestamp"]) for c in tchunks]
        span = (max(stamps) - min(stamps)).days if len(stamps) > 1 else 0
        evidence = "\n".join(f"- ({c['source_type']}) {c['text']}" for c in retrieved)
        prompt = (f"Patient evidence relevant to '{theme}':\n{evidence}\n\n"
                  "Write a short (2-3 sentence), non-diagnostic observation the patient could raise with their "
                  "doctor, based ONLY on the evidence above. Never name a disease. Never add outside medical knowledge.")
        res = await llm.generate(prompt, lang=lang)
        counts: dict[str, int] = {}
        for c in retrieved:
            counts[c["source_type"]] = counts.get(c["source_type"], 0) + 1
        conf, breakdown = composite_confidence(sims, sources, len(tchunks), span)
        breakdown["retrieval"] = method
        breakdown["evidence_count"] = len(tchunks)
        breakdown["span_days"] = span
        insights.append({
            "_id": new_id(), "user_id": user_id, "profile_id": profile_id, "theme": theme,
            "text": res["text"] if res["ok"] else ("Insight narrative is unavailable right now (Gemini is not configured "
                                                    "or unreachable). Your evidence is recorded and shown below."),
            "confidence": conf, "confidence_label": confidence_label(conf),
            "evidence_summary": "based on: " + ", ".join(f"{v} {k}" for k, v in counts.items()),
            "evidence_chunk_ids": [c["_id"] for c in retrieved],
            "generated_by": res["provider"] if res["ok"] else "unavailable",
            "confidence_breakdown": breakdown, "created_at": now_iso()})
    await db.insights.delete_many({"profile_id": profile_id})
    if insights:
        await db.insights.insert_many(insights)
    return insights


async def retrieve_for_query(profile_id: str, query: str, top_k: int = 5) -> list[dict]:
    hits, _ = await search(profile_id, query, top_k)
    return [c for c, _ in hits]


async def delete_by_source(profile_id: str, source_id: str):
    """Removes the evidence chunks created from one record (Mongo + Chroma)."""
    db = get_db()
    ids = [d["_id"] async for d in db.evidence_chunks.find({"profile_id": profile_id, "metadata.source_id": source_id}, {"_id": 1})]
    if ids:
        await db.evidence_chunks.delete_many({"_id": {"$in": ids}})
        await vector.delete_ids(ids)
