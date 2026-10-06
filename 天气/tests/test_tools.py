from 天气.models import WeatherInput,SearchInput
from 天气.tools import run_weather,run_search
from unittest.mock import Mock




def test_run_weather_returns_weather_data(
        weather_input : WeatherInput,
        fake_forecast: list[dict],
        monkeypatch):

    mock_get_forecast = Mock(
        return_value=fake_forecast
    )


    monkeypatch.setattr(
        "天气.tools.get_weather_forecast",
        mock_get_forecast,
    )


    result = run_weather(weather_input)

    assert result["tool"] == "weather"
    assert result["city"] == "Guangzhou"
    assert result["days"] == 3
    assert result["forecast"] == fake_forecast

    mock_get_forecast.assert_called_once_with(
        city="Guangzhou",
        days=3
    )


def test_run_search_returns_search_data():
    search_input = SearchInput(
        keyword="Python Agent",
        limit=5,
    )

    result = run_search(search_input)

    assert result["tool"] == "search"
    assert result["keyword"] == "Python Agent"
    assert result["limit"] == 5



def test_weather_fixture_can_be_changed(
    weather_input: WeatherInput,
):
    weather_input.days = 7

    assert weather_input.days == 7


def test_weather_fixture_starts_fresh(
    weather_input: WeatherInput,
):
    assert weather_input.days == 3
