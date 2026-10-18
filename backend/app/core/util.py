import uuid
from datetime import date, datetime, timezone


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_iso() -> str:
    return date.today().isoformat()


def clean(doc: dict | None) -> dict | None:
    """Mongo document -> API shape (rename _id to id, drop sensitive fields)."""
    if doc is None:
        return None
    out = dict(doc)
    out["id"] = out.pop("_id")
    out.pop("password_hash", None)
    return out


def clean_many(docs: list[dict]) -> list[dict]:
    return [clean(d) for d in docs]
