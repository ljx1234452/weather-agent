import hashlib
import secrets


def create_conversation_key(session_id: str) -> str:
    random_part = secrets.token_urlsafe(32)
    return f"{session_id}_{random_part}"


def hash_conversation_key(conversation_key: str) -> str:
    key_bytes = conversation_key.encode("utf-8")
    hash_object = hashlib.sha256(key_bytes)
    return hash_object.hexdigest()