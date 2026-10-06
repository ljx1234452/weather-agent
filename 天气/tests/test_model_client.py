import json
from unittest.mock import Mock

import pytest

from 天气 import model_client
from 天气.results import ToolResult
from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    Function,
)

from 天气.model_client import extract_raw_call


@pytest.fixture(autouse=True)
def mock_client(monkeypatch) -> Mock:
    fake_client = Mock()
    monkeypatch.setattr(model_client, "client", fake_client)
    return fake_client


def test_missing_model_configuration_has_clear_error(monkeypatch) -> None:
    monkeypatch.setattr(model_client, "client", None)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_BASE_URL", raising=False)

    with pytest.raises(model_client.ModelConfigurationError) as error:
        model_client.get_client()

    assert "MODEL_API_KEY" in str(error.value)
    assert "MODEL_BASE_URL" in str(error.value)



def create_weather_tool_message(
    days: int,
) -> ChatCompletionMessage:
    return ChatCompletionMessage(
        role="assistant",
        content=None,
        tool_calls=[
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                type="function",
                function=Function(
                    name="weather",
                    arguments=json.dumps({
                        "city": "Zhaoqing",
                        "days": days,
                    }),
                ),
            )
        ],
    )



def test_extract_raw_call_returns_dict() -> None:
    message = create_weather_tool_message(days=1)

    result = extract_raw_call(message)

    assert result == {
        "tool_name": "weather",
        "arguments": {
            "city": "Zhaoqing",
            "days": 1,
        },
    }


def test_extract_raw_call_returns_none_without_tool_call() -> None:
    message = ChatCompletionMessage(
        role="assistant",
        content="你好，我是天气助手。",
        tool_calls=None,
    )

    result = extract_raw_call(message)

    assert result is None


def test_run_agent_corrects_validation_error_in_loop(
    monkeypatch,
) -> None:
    wrong_message = create_weather_tool_message(days=10)
    corrected_message = create_weather_tool_message(days=7)

    final_message = ChatCompletionMessage(
        role="assistant",
        content="参数修正成功",
        tool_calls=None,
    )

    validation_error = ToolResult(
        status="error",
        error_type="validation",
        error="days必须小于等于7",
    )

    success_result = ToolResult(
        status="success",
        data={
            "forecast": [],
        },
    )

    mock_create = Mock(
        side_effect=[
            Mock(choices=[
                Mock(message=wrong_message)
            ]),
            Mock(choices=[
                Mock(message=corrected_message)
            ]),
            Mock(choices=[
                Mock(message=final_message)
            ]),
        ]
    )

    mock_handle_tool_call = Mock(
        side_effect=[
            validation_error,
            success_result,
        ]
    )

    monkeypatch.setattr(
        model_client.client.chat.completions,
        "create",
        mock_create,
    )

    monkeypatch.setattr(
        model_client,
        "handle_tool_call",
        mock_handle_tool_call,
    )

    answer = model_client.run_agent(
        "查询肇庆未来10天天气",
        [],
    )

    assert answer == "参数修正成功"
    assert mock_create.call_count == 3
    assert mock_handle_tool_call.call_count == 2

    first_raw_call = (
        mock_handle_tool_call.call_args_list[0].args[0]
    )
    corrected_raw_call = (
        mock_handle_tool_call.call_args_list[1].args[0]
    )

    assert first_raw_call["arguments"]["days"] == 10
    assert corrected_raw_call["arguments"]["days"] == 7


def test_run_agent_returns_tool_result_to_model(monkeypatch) -> None:
    tool_message = create_weather_tool_message(days=1)
    final_message = ChatCompletionMessage(
        role="assistant",
        content="肇庆今天最高温 30 度。",
        tool_calls=None,
    )
    mock_create = Mock(side_effect=[
        Mock(choices=[Mock(message=tool_message)]),
        Mock(choices=[Mock(message=final_message)]),
    ])
    monkeypatch.setattr(
        model_client.client.chat.completions,
        "create",
        mock_create,
    )
    monkeypatch.setattr(
        model_client,
        "handle_tool_call",
        Mock(return_value=ToolResult(
            status="success",
            data={"forecast": [{"max_temperature": 30}]},
        )),
    )

    answer = model_client.run_agent("查询肇庆天气", [])

    assert answer == "肇庆今天最高温 30 度。"
    messages = mock_create.call_args_list[1].kwargs["messages"]
    assert messages[-2]["role"] == "assistant"
    assert messages[-2]["tool_calls"][0]["id"] == "call_1"
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["tool_call_id"] == "call_1"
    assert json.loads(messages[-1]["content"])["status"] == "success"


def test_run_agent_sends_invalid_json_back_for_correction(monkeypatch) -> None:
    invalid_message = ChatCompletionMessage(
        role="assistant",
        content=None,
        tool_calls=[ChatCompletionMessageFunctionToolCall(
            id="call_bad",
            type="function",
            function=Function(name="weather", arguments="{bad json"),
        )],
    )
    final_message = ChatCompletionMessage(
        role="assistant",
        content="参数格式有误",
        tool_calls=None,
    )
    mock_create = Mock(side_effect=[
        Mock(choices=[Mock(message=invalid_message)]),
        Mock(choices=[Mock(message=final_message)]),
    ])
    mock_handle = Mock()
    monkeypatch.setattr(model_client.client.chat.completions, "create", mock_create)
    monkeypatch.setattr(model_client, "handle_tool_call", mock_handle)

    assert model_client.run_agent("查询肇庆天气", []) == "参数格式有误"
    mock_handle.assert_not_called()
    tool_result = mock_create.call_args_list[1].kwargs["messages"][-1]
    assert tool_result["tool_call_id"] == "call_bad"
    assert json.loads(tool_result["content"])["error_type"] == "validation"


def test_run_agent_does_not_retry_network_error(
    monkeypatch,
) -> None:
    message = create_weather_tool_message(days=1)

    network_error = ToolResult(
        status="error",
        error_type="network",
        error="天气服务响应超时",
    )

    mock_handle_tool_call = Mock(
        return_value=network_error
    )
    mock_create = Mock(
        return_value=Mock(choices=[Mock(message=message)])
    )
    monkeypatch.setattr(
        model_client,
        "handle_tool_call",
        mock_handle_tool_call,
    )
    monkeypatch.setattr(
        model_client.client.chat.completions,
        "create",
        mock_create,
    )

    answer = model_client.run_agent(
        "查询肇庆天气",
        [],
    )

    assert answer == "天气服务响应超时"
    assert mock_handle_tool_call.call_count == 1
    assert mock_create.call_count == 1
