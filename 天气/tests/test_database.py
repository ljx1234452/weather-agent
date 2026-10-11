import sqlite3

import pytest

from 天气 import database
from 天气.access_keys import create_conversation_key, hash_conversation_key


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test_agent.db")


def test_save_session_with_key_persists_session_and_hash():
    database.initialize_database()
    conversation_key = create_conversation_key("new-session")
    key_hash = hash_conversation_key(conversation_key)

    database.save_session_with_key("new-session", key_hash)

    assert database.session_exists("new-session")
    assert database.load_messages("new-session") == []
    with database.get_connection() as connection:
        stored_rows = connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall()
    assert stored_rows == [(key_hash, "new-session")]
    assert conversation_key not in stored_rows[0]


def test_save_session_with_key_rolls_back_when_hash_already_exists():
    database.initialize_database()
    database.save_session_with_key("first-session", "a" * 64)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        database.save_session_with_key("new-session", "a" * 64)

    assert not database.session_exists("new-session")
    assert database.session_exists("first-session")
    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall() == [("a" * 64, "first-session")]


def test_save_session_with_key_does_not_add_key_for_duplicate_session():
    database.initialize_database()
    database.save_session_with_key("existing-session", "a" * 64)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        database.save_session_with_key("existing-session", "b" * 64)

    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall() == [("a" * 64, "existing-session")]


def test_initialize_database_preserves_legacy_history_and_key_mapping():
    # 模拟升级前只有 sessions 和 messages 两张表的数据库。
    with database.get_connection() as connection:
        connection.execute(
            "CREATE TABLE sessions (session_id TEXT PRIMARY KEY)"
        )
        connection.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            """
        )
        connection.execute(
            "INSERT INTO sessions (session_id) VALUES (?)",
            ("legacy-session",),
        )
        connection.executemany(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            [
                ("legacy-session", "user", "广州天气"),
                ("legacy-session", "assistant", "以前保存的回答"),
            ],
        )

    database.initialize_database()

    with database.get_connection() as connection:
        assert connection.execute("SELECT * FROM session_keys").fetchall() == []
        connection.execute(
            "INSERT INTO session_keys (key_hash, session_id) VALUES (?, ?)",
            ("a" * 64, "legacy-session"),
        )

    # 再次启动时，旧聊天和新增的钥匙关联都应保留。
    database.initialize_database()

    assert database.session_exists("legacy-session")
    assert database.load_messages("legacy-session") == [
        {"role": "user", "content": "广州天气"},
        {"role": "assistant", "content": "以前保存的回答"},
    ]
    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall() == [("a" * 64, "legacy-session")]


def test_session_key_cannot_reference_unknown_session():
    database.initialize_database()

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        with database.get_connection() as connection:
            connection.execute(
                "INSERT INTO session_keys (key_hash, session_id) VALUES (?, ?)",
                ("a" * 64, "unknown-session"),
            )

    with database.get_connection() as connection:
        assert connection.execute("SELECT * FROM session_keys").fetchall() == []


def test_duplicate_key_hash_cannot_reassign_existing_key():
    database.initialize_database()
    database.save_session("first-session")
    database.save_session("second-session")

    with database.get_connection() as connection:
        connection.execute(
            "INSERT INTO session_keys (key_hash, session_id) VALUES (?, ?)",
            ("a" * 64, "first-session"),
        )

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        with database.get_connection() as connection:
            connection.execute(
                "INSERT INTO session_keys (key_hash, session_id) VALUES (?, ?)",
                ("a" * 64, "second-session"),
            )

    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall() == [("a" * 64, "first-session")]


@pytest.mark.parametrize(
    ("key_hash", "session_id"),
    [(None, "valid-session"), ("a" * 64, None)],
)
def test_session_key_requires_hash_and_session_id(key_hash, session_id):
    database.initialize_database()
    database.save_session("valid-session")

    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed"):
        with database.get_connection() as connection:
            connection.execute(
                "INSERT INTO session_keys (key_hash, session_id) VALUES (?, ?)",
                (key_hash, session_id),
            )


def test_find_session_id_by_key_hash_returns_session_without_changing_keys():
    database.initialize_database()
    conversation_key = create_conversation_key("existing-session")
    key_hash = hash_conversation_key(conversation_key)
    database.save_session_with_key("existing-session", key_hash)

    assert database.find_session_id_by_key_hash(key_hash) == "existing-session"
    assert database.find_session_id_by_key_hash(key_hash) == "existing-session"

    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall() == [(key_hash, "existing-session")]


def test_find_session_id_by_key_hash_keeps_sessions_separate():
    database.initialize_database()
    database.save_session_with_key("first-session", "a" * 64)
    database.save_session_with_key("second-session", "b" * 64)

    assert database.find_session_id_by_key_hash("a" * 64) == "first-session"
    assert database.find_session_id_by_key_hash("b" * 64) == "second-session"


def test_find_session_id_by_key_hash_returns_none_for_empty_table():
    database.initialize_database()

    assert database.find_session_id_by_key_hash("a" * 64) is None


@pytest.mark.parametrize("key_hash", ["b" * 64, "", "' OR 1=1 --"])
def test_find_session_id_by_key_hash_returns_none_without_creating_session(key_hash):
    database.initialize_database()
    database.save_session_with_key("existing-session", "a" * 64)

    assert database.find_session_id_by_key_hash(key_hash) is None

    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT session_id FROM sessions"
        ).fetchall() == [("existing-session",)]
        assert connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall() == [("a" * 64, "existing-session")]


def test_find_session_id_by_key_hash_rejects_tampered_key_with_same_uuid():
    database.initialize_database()
    session_id = "00000000-0000-0000-0000-000000000001"
    conversation_key = create_conversation_key(session_id)
    key_hash = hash_conversation_key(conversation_key)
    database.save_session_with_key(session_id, key_hash)

    replacement = "A" if conversation_key[-1] != "A" else "B"
    tampered_key = conversation_key[:-1] + replacement

    assert tampered_key.startswith(f"{session_id}_")
    assert database.find_session_id_by_key_hash(key_hash) == session_id
    assert database.find_session_id_by_key_hash(
        hash_conversation_key(tampered_key)
    ) is None


def test_find_session_id_by_key_hash_rejects_unhashed_key():
    database.initialize_database()
    conversation_key = create_conversation_key("existing-session")
    database.save_session_with_key(
        "existing-session", hash_conversation_key(conversation_key)
    )

    assert database.find_session_id_by_key_hash(conversation_key) is None
