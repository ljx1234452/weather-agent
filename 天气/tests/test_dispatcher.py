import pytest
from pydantic import ValidationError
from 天气.dispatcher import parse_tool_call


def test_unknown_tool_raises_value_error():
    raw_call = {
        "tool_name": "calculator",
        "arguments": {},
    }

    with pytest.raises(
        ValueError,
        match="不支持的工具",
    ):
        parse_tool_call(raw_call)


def test_invalid_weather_days_raises_validation_error():
    raw_call = {
        "tool_name": "weather",
        "arguments": {
            "city": "Guangzhou",
            "days": 10,
        },
    }

    with pytest.raises(ValidationError)as error_info:
        parse_tool_call(raw_call)

    first_error = error_info.value.errors()[0]

    assert first_error["loc"] == ("arguments","days")
    assert first_error["input"] == 10