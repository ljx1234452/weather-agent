from 天气.models import (
    SearchInput,
    WeatherInput,
)
from 天气.api_client import FORECAST_URL, get_weather_forecast



def run_search(search_input: SearchInput) -> dict:
    return {
        "tool": "search",
        "keyword": search_input.keyword,
        "limit": search_input.limit,
    }


def run_weather(weather_input: WeatherInput) -> dict:

    forecast = get_weather_forecast(
        city=weather_input.city,
        days=weather_input.days
    )


    return {
        "tool": "weather",
        "city": weather_input.city,
        "days": weather_input.days,
        "forecast": forecast
    }
