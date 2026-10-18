"""EchoCare Agent Orchestrator: a tool-using agent with an explicit, auditable routing policy.

Tools: safety_check (always FIRST) -> followup -> rag_search (ChromaDB) -> web_search (Tavily, only when needed)
-> gemini_generate (language-aware). Deterministic by design: in healthcare an agent that might skip the
safety check or loop unpredictably is a liability."""
import re

from app.services import i18n, llm, rag
from app.services.safety import EMERGENCY_MESSAGE, EMERGENCY_RESOURCES, check_emergency

WEB_TRIGGERS = re.compile(
    r"\b(latest|research|guideline|recommend|should i|what is|what are|causes of|treatment for|"
    r"how to|tips for|is it normal|normal range|risk factor)\b", re.IGNORECASE)
DETAIL = {
    "duration": re.compile(r"\b(\d+\s*(day|days|week|weeks|month|months|year|years|hour|hours)|since|for a (day|week|month|year)|"
                           r"yesterday|last night|few (days|weeks|months)|days|weeks|months)\b", re.I),
    "severity": re.compile(r"\b(\d{1,2}\s*/\s*10|\d{1,2} out of 10|mild|moderate|severe|unbearable|slight|worst|terrible)\b", re.I),
    "trigger": re.compile(r"\b(after|before|when|while|during|triggered|worse|better|morning|evening|night|eating|exercise|"
                          r"walking|stress|lying|standing|food)\b", re.I),
}
QKEY = {"duration": "q_duration", "severity": "q_severity", "trigger": "q_trigger"}


def needs_web(query: str, hits: list) -> bool:
    return bool(WEB_TRIGGERS.search(query)) or len(hits) == 0


def missing_details(text: str) -> list[str]:
    return [k for k, p in DETAIL.items() if not p.search(text)]


def followup_questions(message: str, history: list[dict] | None):
    history = history or []
    last_a = next((m for m in reversed(history) if m["role"] == "assistant"), None)
    if last_a and last_a.get("kind") == "followup":
        return None
    if rag.tag_themes(message) == ["general_wellbeing"]:
        return None
    if WEB_TRIGGERS.search(message) and "?" in message:
        return None
    miss = missing_details(message)
    return miss if len(miss) >= 2 else None


def _history_block(history, limit=6):
    if not history:
        return "(this is the start of the conversation)"
    return "\n".join(f"{m['role']}: {m['content']}" for m in history[-limit:])


async def run_agent(profile_id: str, message: str, history: list[dict] | None, lang: str = "en") -> dict:
    if check_emergency(message):
        return {"content": EMERGENCY_MESSAGE, "is_emergency": True, "tools_used": ["safety_check"], "rag_chunk_ids": [],
                "web_sources": [], "resources": [{"label": a, "value": b} for a, b in EMERGENCY_RESOURCES], "kind": None,
                "retrieval": None}
    tools = ["safety_check"]
    miss = followup_questions(message, history)
    if miss:
        qs = "\n".join(f"{i}. {i18n.t(QKEY[k], lang)}" for i, k in enumerate(miss, 1))
        return {"content": f"{i18n.t('followup_intro', lang)}\n{qs}", "is_emergency": False, "tools_used": tools + ["followup"],
                "rag_chunk_ids": [], "web_sources": [], "kind": "followup", "retrieval": None}
    last_user = next((m["content"] for m in reversed(history or []) if m["role"] == "user"), "")
    query = f"{last_user} {message}".strip() if history and history[-1].get("kind") == "followup" else message
    hits, method = await rag.search_chroma(profile_id, query, 5)
    chunks = [c for c, _ in hits]
    tools.append("rag_search")
    web = []
    if needs_web(query, chunks):
        r = await llm.tavily_search(query, 3)
        if r["ok"]:
            web = r["results"]
            tools.append("web_search")
    evidence = "\n".join(f"- ({c['source_type']}) {c['text']}" for c in chunks) or "(no prior evidence on file yet)"
    webtxt = "\n".join(f"- {r['title']}: {(r.get('content') or '')[:200]}" for r in web if r.get("content")) or "(none)"
    prompt = (f"Conversation so far:\n{_history_block(history)}\n\nPatient's own health history (private records):\n{evidence}\n\n"
              f"General web context (not patient-specific):\n{webtxt}\n\nPatient says: {message}\n\n"
              "Answer using the patient's own history first; use web context only for general background. "
              "Do not diagnose. If asked for a diagnosis or treatment plan, say you can't provide one and "
              "suggest discussing it with a clinician.")
    res = await llm.generate(prompt, lang=lang)
    if res["ok"]:
        tools.append("gemini_generate")
    content = res["text"] if res["ok"] else i18n.t("no_llm", lang)
    return {"content": content, "is_emergency": False, "tools_used": tools, "rag_chunk_ids": [c["_id"] for c in chunks],
            "web_sources": web, "kind": None, "retrieval": method, "llm_reason": None if res["ok"] else res.get("reason")}
