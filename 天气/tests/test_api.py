from fastapi.testclient import TestClient
from unittest.mock import Mock
from 天气.api import app
from 天气 import database
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
def session_id() -> str:
    response = client.post("/sessions")

    return response.json()["session_id"]


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_agent_answer(
    monkeypatch,
    session_id: str,
):
    mock_run_agent = Mock(
        return_value="模拟的 Agent 回答"
    )

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        json={
            "message": "广州天气",
            "session_id": session_id,
              },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "模拟的 Agent 回答"
    }

    mock_run_agent.assert_called_once_with(
        user_message="广州天气",
        history=[],
    )


def test_chat_rejects_wrong_access_key(monkeypatch, session_id: str):
    mock_run_agent = Mock()
    monkeypatch.setattr("天气.api.run_agent", mock_run_agent)

    response = client.post(
        "/chat",
        headers={"X-Chat-Key": "wrong-key"},
        json={"session_id": session_id, "message": "广州天气"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "聊天访问口令错误"}
    mock_run_agent.assert_not_called()
    assert database.load_messages(session_id) == []


def test_chat_rejects_blank_message(monkeypatch):
    mock_run_agent = Mock()

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        json={
        "session_id": "conversation-001",
        "message": "     ",
},
    )

    assert response.status_code == 422
    assert (
        "消息不能为空"
        in response.json()["detail"][0]["msg"]
    )
    mock_run_agent.assert_not_called()


def test_chat_returns_503_when_model_unavailable(
    monkeypatch,
    session_id: str,
    caplog,
):
    mock_run_agent = Mock(
        side_effect=OpenAIError("模拟模型故障")
    )

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "广州天气"
            },
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
    session_id: str,
):
    monkeypatch.setattr(
        "天气.api.run_agent",
        Mock(side_effect=ModelConfigurationError("缺少模型配置：MODEL_API_KEY")),
    )

    response = client.post(
        "/chat",
        json={"session_id": session_id, "message": "广州天气"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "缺少模型配置：MODEL_API_KEY"}


def test_chat_rejects_missing_message(monkeypatch):
    mock_run_agent = Mock()

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "conversation-001"
        },
    )

    assert response.status_code == 422
    mock_run_agent.assert_not_called()


def test_chat_isolates_different_sessions(
    monkeypatch,
    session_id: str,
):
    mock_run_agent = Mock(return_value="模拟回答")

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    second_session_response = client.post("/sessions")
    second_session_id = second_session_response.json()[
        "session_id"
    ]

    # 第一轮提问
    first_response = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "广州未来三天天气",
        },
    )
    assert first_response.status_code == 200

    # 不同会话，第一次提问
    second_response = client.post(
        "/chat",
        json={
            "session_id": second_session_id,
            "message": "北京天气",
        },
    )
    assert second_response.status_code == 200

    assert mock_run_agent.call_count == 2

    mock_run_agent.assert_called_with(
        user_message="北京天气",
        history=[],
    )


def test_chat_reuses_session_history(
    monkeypatch,
    session_id: str,
):
    mock_run_agent = Mock(return_value="模拟回答")

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "广州未来三天天气",
        },
    )

    client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "那明天呢？",
        },
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


def test_create_session_returns_new_id():
    response = client.post("/sessions")

    assert response.status_code == 201

    session_id = response.json()["session_id"]

    assert isinstance(session_id, str)
    assert session_id != ""
    assert database.session_exists(session_id)
    assert database.load_messages(session_id) == []


def test_create_sessions_returns_different_ids():
    first_response = client.post("/sessions")
    second_response = client.post("/sessions")


    first_session_id = first_response.json()["session_id"]
    second_session_id = second_response.json()["session_id"]

    assert first_session_id != second_session_id


def test_chat_rejects_unknown_session(monkeypatch):
    mock_run_agent = Mock(
        return_value="模拟的 Agent 回答"
    )

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "unknown-session",
            "message": "广州天气",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "会话编号不存在"
    }
    mock_run_agent.assert_not_called()


def test_get_session_history_returns_empty_messages(
    session_id: str,
):
    response = client.get(
        f"/sessions/{session_id}/history"
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": session_id,
        "messages": [],
    }


def test_get_session_history_returns_saved_messages(
    monkeypatch,
    session_id: str,
):
    mock_run_agent = Mock(
        return_value="广州今天是晴天"
    )

    monkeypatch.setattr(
        "天气.api.run_agent",
        mock_run_agent,
    )

    chat_response = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "广州天气",
        },
    )

    assert chat_response.status_code == 200

    history_response = client.get(
        f"/sessions/{session_id}/history"
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


def test_get_session_history_rejects_unknown_session():
    response = client.get(
    "/sessions/unknown-session/history"
)
    assert response.status_code == 404
    assert response.json() == {
        "detail": "会话编号不存在"
    }


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
