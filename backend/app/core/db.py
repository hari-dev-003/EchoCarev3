"""MongoDB access (Motor). Atlas in production; mongomock-motor in-memory for demo / tests."""
import logging

from app.core.config import get_settings

log = logging.getLogger("echocare.db")
_client = None
_db = None
BACKEND_IN_USE = "uninitialised"

INDEXES = {
    "users": [("email", True)],
    "profiles": [("user_id", False)],
    "evidence_chunks": [("profile_id", False), ("source_type", False)],
    "tracker_entries": [("profile_id", False), ("entry_date", False)],
    "vitals": [("profile_id", False), ("entry_date", False)],
    "reports": [("profile_id", False)],
    "medicines": [("profile_id", False)],
    "appointments": [("profile_id", False)],
    "audit_logs": [("user_id", False), ("created_at", False)],
    "notifications": [("user_id", False), ("created_at", False)],
}


async def connect() -> None:
    global _client, _db, BACKEND_IN_USE
    s = get_settings()
    if s.use_mock_db:
        from mongomock_motor import AsyncMongoMockClient
        _client = AsyncMongoMockClient()
        BACKEND_IN_USE = "mock (in-memory)"
        log.warning("Using IN-MEMORY mock database. Set MONGODB_URI for MongoDB Atlas persistence.")
    else:
        from motor.motor_asyncio import AsyncIOMotorClient
        _client = AsyncIOMotorClient(s.MONGODB_URI, serverSelectionTimeoutMS=8000, appname="EchoCare")
        BACKEND_IN_USE = "MongoDB Atlas"
    _db = _client[s.MONGODB_DB_NAME]
    try:
        for coll, idxs in INDEXES.items():
            for field, unique in idxs:
                await _db[coll].create_index(field, unique=unique)
    except Exception as e:  # never block start-up on index creation (e.g. Atlas IP not yet allow-listed)
        log.error("Index creation failed: %s", e)


async def ping() -> tuple[bool, str]:
    try:
        await _db.command("ping")
        return True, BACKEND_IN_USE
    except Exception as e:
        return False, f"{BACKEND_IN_USE}: {e}"


async def disconnect() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = _db = None


def get_db():
    if _db is None:
        raise RuntimeError("Database not connected")
    return _db
