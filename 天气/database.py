import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

configured_path = os.getenv("WEATHER_DATABASE_PATH")

if configured_path:
    DATABASE_PATH = Path(configured_path)
    if not DATABASE_PATH.is_absolute():
        raise ValueError("WEATHER_DATABASE_PATH 必须是绝对路径")
else:
    DATABASE_PATH = Path(__file__).resolve().parent / "weather_agent.db"


@contextmanager
def get_connection() -> Generator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()

def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS session_keys (
                key_hash TEXT PRIMARY KEY NOT NULL,
                session_id TEXT NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(session_id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(session_id)
            )
            """
        )

def save_session(session_id: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (session_id)
            VALUES (?)
            """,
            (session_id,),
        )

def save_session_with_key(
    session_id: str,
    key_hash: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO sessions (session_id) VALUES (?)",
            (session_id,),
        )

        connection.execute(
            """
            INSERT INTO session_keys (key_hash, session_id)
            VALUES (?, ?)
            """,
            (key_hash, session_id),
        )

def find_session_id_by_key_hash(
    key_hash: str,
) -> str | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT session_id
            FROM session_keys
            WHERE key_hash = ?
            """,
            (key_hash,),
        ).fetchone()

    if row is None:
        return None

    return row[0]

def save_message(
    session_id: str,
    role: str,
    content: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO messages (
                session_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
            ),
        )

def save_chat_messages(
    session_id: str,
    user_content: str,
    assistant_content: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO messages (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, "user", user_content),
        )
        connection.execute(
            """
            INSERT INTO messages (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, "assistant", assistant_content),
        )

def load_messages(
    session_id: str,
) -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

    return [
        {
            "role": role,
            "content": content,
        }
        for role, content in rows
    ]


def session_exists(session_id: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    return row is not None


if __name__ == "__main__":
    initialize_database()
    print(f"数据库位置：{DATABASE_PATH}")
