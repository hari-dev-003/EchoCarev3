"""Alg. 5 department recommendation: trained TF-IDF + LogisticRegression, transparent keyword fallback."""
from pathlib import Path

from app.data.specialties import KEYWORD_TO_SPECIALTY

MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "department_model.joblib"
_model = None


def _load():
    global _model
    if _model is None and MODEL_PATH.exists():
        import joblib
        _model = joblib.load(MODEL_PATH)
    return _model


def model_available() -> bool:
    return MODEL_PATH.exists()


def predict_department(text: str) -> dict:
    model = _load()
    if model is not None:
        proba = model.predict_proba([text])[0]
        ranked = sorted(zip(model.classes_, proba), key=lambda x: x[1], reverse=True)[:3]
        return {"model_used": "trained_classifier (tfidf + logistic regression)", "top_department": str(ranked[0][0]),
                "confidence": float(ranked[0][1]), "ranked": [{"department": str(d), "score": float(s)} for d, s in ranked]}
    tl = text.lower()
    scores: dict[str, int] = {}
    for kw, sp in KEYWORD_TO_SPECIALTY.items():
        if kw in tl:
            scores[sp] = scores.get(sp, 0) + 1
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    total = sum(scores.values()) or 1
    return {"model_used": "keyword_heuristic_fallback (train: python ml/train_department_classifier.py)",
            "top_department": ranked[0][0] if ranked else "General Medicine",
            "confidence": (ranked[0][1] / total) if ranked else 0.3,
            "ranked": [{"department": d, "score": s / total} for d, s in ranked[:3]]}
