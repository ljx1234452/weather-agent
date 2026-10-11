from fastapi.testclient import TestClient
from unittest.mock import Mock
from uuid import UUID
from 天气.api import app
from 天气 import database
from 天气.access_keys import create_conversation_key, hash_conversation_key
from openai import OpenAIError
from 天气.model_client import ModelConfigurationError
import pytest
import sqlite3
import logging




client = TestClient(app)
client.headers["X-Chat-Key"] = "test-chat-key"
@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_ACCESS_KEY", "test-chat-key")
    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        tmp_path / "weather_agent.db",
    )
    database.initialize_database()


@pytest.fixture
def created_session() -> dict[str, str]:
    response = client.post("/sessions")

    assert response.status_code == 201
    return response.json()


@pytest.fixture
def session_id(created_session: dict[str, str]) -> str:
    return created_session["session_id"]


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_agent_answer(
    monkeypatch,
    created_session: dict[str, str],
    caplog,
):
    mock_run_agent = Mock(
        return_value="模拟的 Agent 回答"
    )

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    with caplog.at_level(logging.INFO, logger="天气.api"):
        response = TestClient(app).post(
            "/chat",
            headers={"X-Conversation-Key": created_session["conversation_key"]},
            json={"message": "广州天气"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "模拟的 Agent 回答"
    }

    mock_run_agent.assert_called_once_with(
        user_message="广州天气",
        history=[],
    )
    assert database.load_messages(created_session["session_id"]) == [
        {"role": "user", "content": "广州天气"},
        {"role": "assistant", "content": "模拟的 Agent 回答"},
    ]
    assert created_session["conversation_key"] not in caplog.text
    assert created_session["conversation_key"] not in response.text


@pytest.mark.parametrize("key_kind", ["unknown", "tampered", "session_id_only"])
def test_chat_rejects_invalid_conversation_key(
    monkeypatch,
    created_session: dict[str, str],
    key_kind: str,
):
    session_id = created_session["session_id"]
    original_key = created_session["conversation_key"]
    if key_kind == "unknown":
        invalid_key = create_conversation_key("unknown-session")
    elif key_kind == "tampered":
        replacement = "A" if original_key[-1] != "A" else "B"
        invalid_key = original_key[:-1] + replacement
    else:
        invalid_key = session_id

    mock_run_agent = Mock()
    mock_load_messages = Mock()
    mock_save_messages = Mock()
    monkeypatch.setattr("天气.api.run_agent", mock_run_agent)
    monkeypatch.setattr("天气.api.load_messages", mock_load_messages)
    monkeypatch.setattr("天气.api.save_chat_messages", mock_save_messages)

    response = client.post(
        "/chat",
        headers={"X-Conversation-Key": invalid_key},
        json={"session_id": session_id, "message": "广州天气"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "对话钥匙无效"}
    assert invalid_key not in response.text
    mock_run_agent.assert_not_called()
    mock_load_messages.assert_not_called()
    mock_save_messages.assert_not_called()
    assert database.load_messages(session_id) == []


def test_chat_rejects_blank_message(monkeypatch, created_session: dict[str, str]):
    mock_run_agent = Mock()

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "     "},
    )

    assert response.status_code == 422
    assert (
        "消息不能为空"
        in response.json()["detail"][0]["msg"]
    )
    mock_run_agent.assert_not_called()


def test_chat_returns_503_when_model_unavailable(
    monkeypatch,
    created_session: dict[str, str],
    caplog,
):
    session_id = created_session["session_id"]
    mock_run_agent = Mock(
        side_effect=OpenAIError("模拟模型故障")
    )

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "广州天气"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "模型服务暂时不可用"
    }

    mock_run_agent.assert_called_once_with(
        user_message="广州天气",
        history=[],
    )

    assert (
        "天气.api",
        logging.ERROR,
        f"模型服务调用失败：session_id={session_id}",
        ) in caplog.record_tuples

def test_chat_reports_missing_model_configuration(
    monkeypatch,
    created_session: dict[str, str],
):
    monkeypatch.setattr(
        "天气.api.run_agent",
        Mock(side_effect=ModelConfigurationError("缺少模型配置：MODEL_API_KEY")),
    )

    response = client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "广州天气"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "缺少模型配置：MODEL_API_KEY"}


def test_chat_rejects_missing_message(monkeypatch, created_session: dict[str, str]):
    mock_run_agent = Mock()

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={},
    )

    assert response.status_code == 422
    mock_run_agent.assert_not_called()


def test_chat_isolates_different_sessions(
    monkeypatch,
    created_session: dict[str, str],
):
    mock_run_agent = Mock(return_value="模拟回答")

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    second_session_response = client.post("/sessions")
    assert second_session_response.status_code == 201
    second_session = second_session_response.json()

    # 第一轮提问
    first_response = client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "广州未来三天天气"},
    )
    assert first_response.status_code == 200

    # 不同会话，第一次提问
    second_response = client.post(
        "/chat",
        headers={"X-Conversation-Key": second_session["conversation_key"]},
        json={"message": "北京天气"},
    )
    assert second_response.status_code == 200

    assert mock_run_agent.call_count == 2

    mock_run_agent.assert_called_with(
        user_message="北京天气",
        history=[],
    )
    assert database.load_messages(created_session["session_id"]) == [
        {"role": "user", "content": "广州未来三天天气"},
        {"role": "assistant", "content": "模拟回答"},
    ]
    assert database.load_messages(second_session["session_id"]) == [
        {"role": "user", "content": "北京天气"},
        {"role": "assistant", "content": "模拟回答"},
    ]


def test_chat_reuses_session_history(
    monkeypatch,
    created_session: dict[str, str],
):
    mock_run_agent = Mock(return_value="模拟回答")

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "广州未来三天天气"},
    )

    client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "那明天呢？"},
    )

    mock_run_agent.assert_called_with(
        user_message="那明天呢？",
        history=[
            {
                "role": "user",
                "content": "广州未来三天天气",
            },
            {
                "role": "assistant",
                "content": "模拟回答",
            },
        ],
    )


def test_create_session_returns_new_id_and_conversation_key():
    response = client.post("/sessions")

    assert response.status_code == 201

    response_data = response.json()
    assert set(response_data) == {"session_id", "conversation_key"}
    session_id = response_data["session_id"]
    conversation_key = response_data["conversation_key"]

    assert isinstance(session_id, str)
    assert session_id != ""
    assert UUID(session_id).version == 4
    assert isinstance(conversation_key, str)
    assert conversation_key.startswith(f"{session_id}_")
    assert len(conversation_key.removeprefix(f"{session_id}_")) == 43
    assert database.session_exists(session_id)
    assert database.load_messages(session_id) == []

    with database.get_connection() as connection:
        stored_rows = connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall()
    assert stored_rows == [(hash_conversation_key(conversation_key), session_id)]
    assert conversation_key not in stored_rows[0]


def test_create_session_does_not_log_conversation_key(caplog):
    with caplog.at_level(logging.INFO, logger="天气.api"):
        response = client.post("/sessions")

    assert response.status_code == 201
    response_data = response.json()
    conversation_key = response_data["conversation_key"]
    random_part = conversation_key.removeprefix(f"{response_data['session_id']}_")
    assert "会话保存成功" in caplog.text
    assert conversation_key not in caplog.text
    assert random_part not in caplog.text


def test_create_session_rolls_back_on_key_collision(monkeypatch, caplog):
    generated_keys: list[str] = []

    def record_generated_key(session_id: str) -> str:
        conversation_key = create_conversation_key(session_id)
        generated_keys.append(conversation_key)
        return conversation_key

    monkeypatch.setattr("天气.api.create_conversation_key", record_generated_key)
    monkeypatch.setattr(
        "天气.api.hash_conversation_key",
        Mock(return_value="a" * 64),
    )
    first_response = client.post("/sessions")
    assert first_response.status_code == 201
    first_session_id = first_response.json()["session_id"]

    with TestClient(app, raise_server_exceptions=False) as failing_client:
        response = failing_client.post(
            "/sessions",
            headers={"X-Chat-Key": "test-chat-key"},
        )

    assert response.status_code == 500
    with database.get_connection() as connection:
        assert connection.execute(
            "SELECT session_id FROM sessions"
        ).fetchall() == [(first_session_id,)]
        assert connection.execute(
            "SELECT key_hash, session_id FROM session_keys"
        ).fetchall() == [("a" * 64, first_session_id)]
    assert "会话保存失败" in caplog.text
    for conversation_key in generated_keys:
        assert conversation_key not in caplog.text
        assert conversation_key not in response.text


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Chat-Key": "wrong-key"}],
)
def test_create_session_rejects_invalid_access_key(monkeypatch, headers):
    mock_save_session_with_key = Mock()
    mock_create_key = Mock()
    monkeypatch.setattr("天气.api.save_session_with_key", mock_save_session_with_key)
    monkeypatch.setattr("天气.api.create_conversation_key", mock_create_key)

    response = TestClient(app).post("/sessions", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "聊天访问口令错误"}
    mock_save_session_with_key.assert_not_called()
    mock_create_key.assert_not_called()


def test_create_session_requires_configured_access_key(monkeypatch):
    monkeypatch.delenv("CHAT_ACCESS_KEY")
    mock_save_session_with_key = Mock()
    monkeypatch.setattr("天气.api.save_session_with_key", mock_save_session_with_key)

    response = client.post("/sessions")

    assert response.status_code == 503
    assert response.json() == {"detail": "聊天访问口令未配置"}
    mock_save_session_with_key.assert_not_called()


def test_create_sessions_returns_different_ids():
    first_response = client.post("/sessions")
    second_response = client.post("/sessions")


    first_session_id = first_response.json()["session_id"]
    second_session_id = second_response.json()["session_id"]

    assert first_session_id != second_session_id
    assert first_response.json()["conversation_key"] != second_response.json()[
        "conversation_key"
    ]


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Chat-Key": "test-chat-key"}, {"X-Conversation-Key": ""}],
)
def test_chat_requires_conversation_key(
    monkeypatch,
    created_session: dict[str, str],
    headers: dict[str, str],
):
    mock_run_agent = Mock()
    mock_lookup = Mock()
    mock_load_messages = Mock()
    mock_save_messages = Mock()
    monkeypatch.setattr("天气.api.run_agent", mock_run_agent)
    monkeypatch.setattr("天气.api.find_session_id_by_key_hash", mock_lookup)
    monkeypatch.setattr("天气.api.load_messages", mock_load_messages)
    monkeypatch.setattr("天气.api.save_chat_messages", mock_save_messages)

    response = TestClient(app).post(
        "/chat",
        headers=headers,
        json={"session_id": created_session["session_id"], "message": "广州天气"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "缺少对话钥匙"}
    mock_lookup.assert_not_called()
    mock_run_agent.assert_not_called()
    mock_load_messages.assert_not_called()
    mock_save_messages.assert_not_called()
    assert database.load_messages(created_session["session_id"]) == []


def test_chat_does_not_require_shared_access_key(
    monkeypatch,
    created_session: dict[str, str],
):
    monkeypatch.delenv("CHAT_ACCESS_KEY")
    mock_run_agent = Mock(return_value="模拟回答")
    monkeypatch.setattr("天气.api.run_agent", mock_run_agent)

    response = TestClient(app).post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "你好"},
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "模拟回答"}
    mock_run_agent.assert_called_once_with(user_message="你好", history=[])


def test_chat_uses_key_instead_of_caller_supplied_session_id(
    monkeypatch,
    created_session: dict[str, str],
):
    second_response = client.post("/sessions")
    assert second_response.status_code == 201
    second_session = second_response.json()
    database.save_chat_messages(created_session["session_id"], "我的历史", "我的回答")
    database.save_chat_messages(second_session["session_id"], "另一段历史", "另一段回答")
    mock_run_agent = Mock(return_value="新回答")
    monkeypatch.setattr("天气.api.run_agent", mock_run_agent)

    response = client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "新问题", "session_id": second_session["session_id"]},
    )

    assert response.status_code == 200
    mock_run_agent.assert_called_once_with(
        user_message="新问题",
        history=[
            {"role": "user", "content": "我的历史"},
            {"role": "assistant", "content": "我的回答"},
        ],
    )
    assert database.load_messages(created_session["session_id"])[-2:] == [
        {"role": "user", "content": "新问题"},
        {"role": "assistant", "content": "新回答"},
    ]
    assert database.load_messages(second_session["session_id"]) == [
        {"role": "user", "content": "另一段历史"},
        {"role": "assistant", "content": "另一段回答"},
    ]


def test_chat_docs_only_request_message_and_conversation_key():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    request_schema = schema["components"]["schemas"]["ChatRequest"]

    assert set(request_schema["properties"]) == {"message"}
    assert request_schema["required"] == ["message"]
    assert [
        (parameter["name"].lower(), parameter["in"])
        for parameter in schema["paths"]["/chat"]["post"]["parameters"]
    ] == [("x-conversation-key", "header")]


def test_get_session_history_returns_empty_messages(
    monkeypatch,
    created_session: dict[str, str],
):
    mock_run_agent = Mock()
    monkeypatch.setattr("天气.api.run_agent", mock_run_agent)

    response = TestClient(app).get(
        "/history",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": created_session["session_id"],
        "messages": [],
    }
    mock_run_agent.assert_not_called()


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Chat-Key": "test-chat-key"}, {"X-Conversation-Key": ""}],
)
def test_get_session_history_requires_conversation_key(
    monkeypatch,
    headers: dict[str, str],
):
    mock_find_session = Mock()
    mock_load_messages = Mock()
    monkeypatch.setattr("天气.api.find_session_id_by_key_hash", mock_find_session)
    monkeypatch.setattr("天气.api.load_messages", mock_load_messages)

    response = TestClient(app).get(
        "/history",
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "缺少对话钥匙"}
    mock_find_session.assert_not_called()
    mock_load_messages.assert_not_called()


@pytest.mark.parametrize("key_kind", ["unknown", "tampered"])
def test_get_session_history_rejects_invalid_conversation_key(
    monkeypatch,
    created_session: dict[str, str],
    key_kind: str,
):
    original_key = created_session["conversation_key"]
    if key_kind == "unknown":
        invalid_key = create_conversation_key("unknown-session")
    else:
        replacement = "A" if original_key[-1] != "A" else "B"
        invalid_key = original_key[:-1] + replacement

    mock_load_messages = Mock()
    monkeypatch.setattr("天气.api.load_messages", mock_load_messages)

    response = TestClient(app).get(
        "/history",
        headers={"X-Conversation-Key": invalid_key, "X-Chat-Key": "test-chat-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "对话钥匙无效"}
    assert invalid_key not in response.text
    mock_load_messages.assert_not_called()


def test_get_session_history_does_not_require_shared_access_key(
    monkeypatch,
    created_session: dict[str, str],
):
    # 会话创建完成后，读取历史只依赖该会话自己的钥匙。
    monkeypatch.delenv("CHAT_ACCESS_KEY")

    response = TestClient(app).get(
        "/history",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": created_session["session_id"],
        "messages": [],
    }


def test_get_session_history_returns_saved_messages(
    monkeypatch,
    created_session: dict[str, str],
):
    session_id = created_session["session_id"]
    mock_run_agent = Mock(
        return_value="广州今天是晴天"
    )

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    chat_response = client.post(
        "/chat",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
        json={"message": "广州天气"},
    )

    assert chat_response.status_code == 200

    history_response = TestClient(app).get(
        "/history",
        headers={"X-Conversation-Key": created_session["conversation_key"]},
    )

    assert history_response.status_code == 200
    assert history_response.json() == {
        "session_id": session_id,
        "messages": [
            {
                "role": "user",
                "content": "广州天气",
            },
            {
                "role": "assistant",
                "content": "广州今天是晴天",
            },
        ],
    }
    assert mock_run_agent.call_count == 1


def test_get_session_history_uses_key_to_select_its_own_history(
    created_session: dict[str, str],
):
    second_response = client.post("/sessions")
    assert second_response.status_code == 201
    second_session = second_response.json()

    for session, question, answer in [
        (created_session, "第一段对话的问题", "第一段对话的回答"),
        (second_session, "第二段对话的问题", "第二段对话的回答"),
    ]:
        database.save_chat_messages(session["session_id"], question, answer)

    for session, other_session, question, answer in [
        (created_session, second_session, "第一段对话的问题", "第一段对话的回答"),
        (second_session, created_session, "第二段对话的问题", "第二段对话的回答"),
    ]:
        response = TestClient(app).get(
            "/history",
            headers={"X-Conversation-Key": session["conversation_key"]},
            # 即使额外指定另一个编号，也只能读取钥匙对应的那段历史。
            params={"session_id": other_session["session_id"]},
        )
        assert response.status_code == 200
        assert response.json() == {
            "session_id": session["session_id"],
            "messages": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ],
        }
        assert session["conversation_key"] not in response.text
        assert other_session["conversation_key"] not in response.text


def test_get_session_history_removes_legacy_id_route(
    created_session: dict[str, str],
):
    response = client.get(f"/sessions/{created_session['session_id']}/history")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_save_chat_messages_rolls_back(session_id: str):
    database.save_chat_messages(
        session_id=session_id,
        user_content="广州天气",
        assistant_content="广州今天晴天",
    )

    with pytest.raises(sqlite3.IntegrityError):
        database.save_chat_messages(
            session_id=session_id,
            user_content="北京天气",
            assistant_content=None,
        )

    assert database.load_messages(session_id) == [
        {"role": "user", "content": "广州天气"},
        {"role": "assistant", "content": "广州今天晴天"},
    ]

def test_get_connection_closes_after_with():
    with database.get_connection() as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")

    with pytest.raises(ValueError, match="故意失败"):
        with database.get_connection() as failed_connection:
            raise ValueError("故意失败")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        failed_connection.execute("SELECT 1")
