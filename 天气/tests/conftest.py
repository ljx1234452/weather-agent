import pytest

from 天气.models import WeatherInput



@pytest.fixture(scope = "function")
def weather_input() -> WeatherInput:
    return WeatherInput(
        city="Guangzhou",
        days=3,
    )




@pytest.fixture(scope = "function")
def valid_weather_call(
    weather_input: WeatherInput
) -> dict:
    return {
        "tool_name": "weather",
        "arguments": weather_input.model_dump(),
    }



@pytest.fixture(scope = "function")
def fake_forecast() -> list[dict]:
    return [
        {
            "date": "2026-08-26",
            "max_temperature": 30.0,
            "min_temperature": 25.0,
        },
        {
            "date": "2026-08-27",
            "max_temperature": 31.0,
            "min_temperature": 26.0,
        },
        {
            "date": "2026-08-28",
            "max_temperature": 32.0,
            "min_temperature": 27.0,
        },
    ]
