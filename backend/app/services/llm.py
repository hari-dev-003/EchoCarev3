"""The ONLY external AI APIs: Google Gemini and Tavily. Every function returns {"ok": bool, ...} so an
unconfigured / unreachable provider is reported honestly and never replaced with fabricated content."""
import asyncio
import contextvars
import io
import re
import struct
import wave

from app.core.config import get_settings

SYSTEM_PROMPT = (
    "You are EchoCare's clinical-evidence assistant. You NEVER provide a diagnosis, even implicitly. "
    "You only phrase observations as discussion points for the patient to raise with a licensed "
    "clinician. Ground every statement strictly in the evidence given to you; never use outside medical "
    "knowledge to fill gaps. If evidence is thin, say so plainly. Keep responses concise, warm and non-alarmist."
)
DEFAULT_GEN_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]
LANG_NAMES = {"en": "English", "ta": "Tamil", "hi": "Hindi"}
_client_cache: dict = {}
# Per-request consent flags, set from the signed-in user's Privacy & consent settings (see core/deps.py).
ai_allowed: contextvars.ContextVar[bool] = contextvars.ContextVar("ai_allowed", default=True)
web_allowed: contextvars.ContextVar[bool] = contextvars.ContextVar("web_allowed", default=True)


def gemini_key_present() -> bool:
    return bool(get_settings().GOOGLE_API_KEY.strip())


def gemini_configured() -> bool:
    """True only when a key exists AND the signed-in user has consented to AI processing."""
    return gemini_key_present() and ai_allowed.get()


def tavily_configured() -> bool:
    return bool(get_settings().TAVILY_API_KEY.strip()) and web_allowed.get()


def blocked_by_consent() -> bool:
    return not ai_allowed.get()


def _client():
    key = get_settings().GOOGLE_API_KEY.strip()
    if key not in _client_cache:
        from google import genai
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def _models() -> list[str]:
    cfg = get_settings().GEMINI_MODEL.strip()
    return ([cfg] if cfg else []) + [m for m in DEFAULT_GEN_MODELS if m != cfg]


def _discover_generation_models() -> list[str]:
    """Ask this API key which models it can actually use for generateContent.

    Model availability changes over time and can differ by API project. This is
    only used after the configured/default model names fail.
    """
    try:
        available = _client().models.list()
        found = []
        for model in available:
            actions = getattr(model, "supported_actions", None) or []
            if any("generateContent" in action for action in actions):
                name = getattr(model, "name", "") or ""
                name = name.removeprefix("models/")
                if name:
                    found.append(name)
        return found
    except Exception:
        return []


def _lang_instr(lang: str) -> str:
    name = LANG_NAMES.get(lang, "English")
    return "" if name == "English" else f"\n\nRespond entirely in {name} (keep medical terms understandable)."


def _not_configured(what: str = "GOOGLE_API_KEY") -> dict:
    if gemini_key_present() and not ai_allowed.get():
        return {"ok": False, "text": None, "provider": "gemini", "consent": False,
                "reason": "AI processing is switched off in Privacy & consent, so nothing was sent to Gemini."}
    return {"ok": False, "text": None, "provider": "gemini", "reason": f"{what} is not configured in backend/.env."}


def _generate_sync(contents, system: str, lang: str = "en", json_mode: bool = False) -> dict:
    if not gemini_configured():
        return _not_configured()
    try:
        from google.genai import types
        cfg = types.GenerateContentConfig(system_instruction=system + _lang_instr(lang),
                                          response_mime_type="application/json" if json_mode else None)
        last = None
        attempted = set()
        candidates = _models()
        for model in candidates:
            attempted.add(model)
            try:
                resp = _client().models.generate_content(model=model, contents=contents, config=cfg)
                return {"ok": True, "text": resp.text, "provider": f"gemini ({model})", "reason": None}
            except Exception as e:
                last = e
        # The model catalog is authoritative for this key and prevents a stale
        # hard-coded fallback from making a working Gemini configuration look broken.
        for model in _discover_generation_models():
            if model in attempted:
                continue
            try:
                resp = _client().models.generate_content(model=model, contents=contents, config=cfg)
                return {"ok": True, "text": resp.text, "provider": f"gemini ({model})", "reason": None}
            except Exception as e:
                last = e
        return {"ok": False, "text": None, "provider": "gemini", "reason": str(last)[:300]}
    except Exception as e:
        return {"ok": False, "text": None, "provider": "gemini", "reason": str(e)[:300]}


async def generate(prompt: str, system: str = SYSTEM_PROMPT, lang: str = "en") -> dict:
    return await asyncio.to_thread(_generate_sync, prompt, system, lang)


def _parts(parts):
    from google.genai import types
    return [types.Part.from_bytes(data=b, mime_type=m) for b, m in parts]


async def generate_json(prompt: str, parts: list | None = None, system: str = SYSTEM_PROMPT) -> dict:
    if not gemini_configured():
        return _not_configured()
    contents = (_parts(parts) if parts else []) + [prompt]
    return await asyncio.to_thread(_generate_sync, contents, system, "en", True)


async def vision(parts: list, prompt: str, lang: str = "en", system: str = SYSTEM_PROMPT) -> dict:
    if not gemini_configured():
        return _not_configured()
    return await asyncio.to_thread(_generate_sync, _parts(parts) + [prompt], system, lang)


async def transcribe(audio: bytes, mime: str = "audio/wav") -> dict:
    if not gemini_configured():
        return _not_configured()
    prompt = ("Transcribe this audio exactly as spoken. The speaker may use English, Tamil or Hindi. "
              "Return only the transcript text, in the language spoken, with no commentary.")
    return await asyncio.to_thread(_generate_sync, _parts([(audio, mime)]) + [prompt], "You are a precise speech transcriber.", "en")


# ---------- embeddings ----------
def _embed_sync(texts: list[str], task_type: str) -> list[list[float]] | None:
    if not texts or not gemini_configured():
        return None
    s = get_settings()
    try:
        import numpy as np
        from google.genai import types
        resp = _client().models.embed_content(model=s.EMBED_MODEL, contents=list(texts),
                                              config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=s.EMBED_DIM))
        vecs = [np.array(e.values, dtype=float) for e in resp.embeddings]
        if len(vecs) != len(texts):
            return None
        out = []
        for v in vecs:  # truncated Matryoshka vectors must be re-normalised
            n = np.linalg.norm(v) or 1.0
            out.append((v / n).tolist())
        return out
    except Exception:
        return None


async def embed_gemini(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"):
    return await asyncio.to_thread(_embed_sync, texts, task_type)


# ---------- Tavily ----------
def _tavily_sync(query: str, max_results: int) -> dict:
    if not tavily_configured():
        if get_settings().TAVILY_API_KEY.strip() and not web_allowed.get():
            return {"ok": False, "results": [], "reason": "Web search is switched off in Privacy & consent."}
        return {"ok": False, "results": [], "reason": "TAVILY_API_KEY is not configured in backend/.env."}
    try:
        from tavily import TavilyClient
        resp = TavilyClient(api_key=get_settings().TAVILY_API_KEY.strip()).search(query=query, max_results=max_results)
        return {"ok": True, "reason": None, "results": [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")} for r in resp.get("results", [])]}
    except Exception as e:
        return {"ok": False, "results": [], "reason": str(e)[:300]}


async def tavily_search(query: str, max_results: int = 3) -> dict:
    return await asyncio.to_thread(_tavily_sync, query, max_results)


def parse_json_loose(text):
    from app.services.labs import parse_json_loose as p
    return p(text)
