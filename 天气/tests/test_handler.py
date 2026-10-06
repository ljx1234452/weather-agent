from 天气.handler import handle_tool_call
from unittest.mock import Mock
import requests




def test_weather_success(valid_weather_call: dict,
    fake_forecast: list[dict],
    monkeypatch
    ):
    mock_get_forecast = Mock(
        return_value=fake_forecast
    )

    monkeypatch.setattr(
        "天气.tools.get_weather_forecast",
        mock_get_forecast,
    )

    result = handle_tool_call(valid_weather_call)

    assert result.status == "success"
    assert result.data is not None
    assert result.data["city"] == "Guangzhou"
    assert result.data["days"] == 3
    assert result.data["forecast"] == fake_forecast
    assert result.error is None
    assert result.error_type is None

    mock_get_forecast.assert_called_once_with(
        city="Guangzhou",
        days=3,
    )

def test_unknown_tool_returns_error():
    raw_call = {
        "tool_name": "calculator",
        "arguments": {},
    }

    result = handle_tool_call(raw_call)

    assert result.status == "error"
    assert result.data is None
    assert result.error == "不支持的工具"
    assert result.error_type == "tool"


def test_invalid_weather_days_returns_error():
    raw_call = {
        "tool_name": "weather",
        "arguments":{
            "city":"Guangzhou",
            "days":10
        }
    }

    result = handle_tool_call(raw_call)

    assert result.status == "error"
    assert result.data is None
    assert result.error is not None
    assert "arguments.days" in result.error
    assert result.error_type == "validation"



def test_search_success():
    raw_call = {
        "tool_name": "search",
        "arguments":{
            "keyword":"AI Agent",
            "limit": 5}
    }

    result = handle_tool_call(raw_call)

    assert result.status == "success"
    assert result.data is not None
    assert result.data["tool"] == "search"
    assert result.data["keyword"] == "AI Agent"
    assert result.data["limit"] == 5
    assert result.error is None




def test_weather_timeout_returns_error(
    valid_weather_call: dict,
    monkeypatch,
):
    mock_get_forecast = Mock(
        side_effect=requests.Timeout("请求超时")
    )

    monkeypatch.setattr(
        "天气.tools.get_weather_forecast",
        mock_get_forecast,
    )

    result = handle_tool_call(valid_weather_call)

    assert result.status == "error"
    assert result.data is None
    assert result.error == "天气服务响应超时，请稍后重试"
    assert result.error_type == "network"

    mock_get_forecast.assert_called_once_with(
        city="Guangzhou",
        days=3,
    )


def test_weather_http_error_returns_error(
    valid_weather_call: dict,
    monkeypatch,
):
    mock_get_forecast = Mock(
        side_effect=requests.HTTPError("500 Server Error")
    )

    monkeypatch.setattr(
        "天气.tools.get_weather_forecast",
        mock_get_forecast,
    )

    result = handle_tool_call(valid_weather_call)

    assert result.status == "error"
    assert result.data is None
    assert result.error == "天气服务暂时不可用，请稍后重试"
    assert result.error_type == "network"

    mock_get_forecast.assert_called_once_with(
        city="Guangzhou",
        days=3,
    )