from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from 天气 import api, database
from 天气.access_keys import create_conversation_key, hash_conversation_key


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "conversation_access.db")
    database.initialize_database()


@pytest.fixture
def stored_conversation() -> tuple[str, str]:
    session_id = "conversation-001"
    conversation_key = create_conversation_key(session_id)
    database.save_session_with_key(session_id, hash_conversation_key(conversation_key))
    return session_id, conversation_key


def test_complete_conversation_key_returns_session_id(stored_conversation):
    session_id, conversation_key = stored_conversation

    result = api.require_conversation_key(conversation_key)

    assert isinstance(result, str)
    assert result == session_id


@pytest.mark.parametrize("conversation_key", [None, ""])
def test_missing_conversation_key_is_rejected_before_lookup(monkeypatch, conversation_key):
    mock_hash = Mock()
    mock_lookup = Mock()
    monkeypatch.setattr(api, "hash_conversation_key", mock_hash)
    monkeypatch.setattr(api, "find_session_id_by_key_hash", mock_lookup)

    with pytest.raises(HTTPException) as error:
        api.require_conversation_key(conversation_key)

    assert error.value.status_code == 401
    assert error.value.detail == "缺少对话钥匙"
    mock_hash.assert_not_called()
    mock_lookup.assert_not_called()


def test_unknown_conversation_key_is_rejected_without_leaking_key():
    unknown_key = create_conversation_key("unknown-session")

    with pytest.raises(HTTPException) as error:
        api.require_conversation_key(unknown_key)

    assert error.value.status_code == 401
    assert error.value.detail == "对话钥匙无效"
    assert unknown_key not in error.value.detail


def test_changed_secret_with_same_session_prefix_is_rejected(stored_conversation):
    session_id, conversation_key = stored_conversation
    tampered_key = conversation_key + "-tampered"
    assert tampered_key.startswith(session_id + "_")

    with pytest.raises(HTTPException) as error:
        api.require_conversation_key(tampered_key)

    assert error.value.status_code == 401
    assert error.value.detail == "对话钥匙无效"
    assert tampered_key not in error.value.detail
    assert conversation_key not in error.value.detail


def test_session_id_alone_is_not_a_conversation_key(stored_conversation):
    session_id, _ = stored_conversation

    with pytest.raises(HTTPException) as error:
        api.require_conversation_key(session_id)

    assert error.value.status_code == 401
    assert error.value.detail == "对话钥匙无效"


def test_each_conversation_key_returns_its_own_session(stored_conversation):
    first_session_id, first_key = stored_conversation
    second_session_id = "conversation-002"
    second_key = create_conversation_key(second_session_id)
    database.save_session_with_key(second_session_id, hash_conversation_key(second_key))

    assert api.require_conversation_key(first_key) == first_session_id
    assert api.require_conversation_key(second_key) == second_session_id


def test_repeated_access_does_not_change_database(stored_conversation):
    session_id, conversation_key = stored_conversation
    database.save_chat_messages(session_id, "广州天气", "天气晴朗")
    with database.get_connection() as connection:
        before = list(connection.iterdump())

    assert api.require_conversation_key(conversation_key) == session_id
    assert api.require_conversation_key(conversation_key) == session_id

    with database.get_connection() as connection:
        assert list(connection.iterdump()) == before
