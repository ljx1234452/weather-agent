import logging
import requests
import time
import os
from pathlib import Path
from dotenv import load_dotenv
import math



GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# 加载项目根目录的 .env 文件。
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MAX_ATTEMPTS = int(os.getenv("WEATHER_MAX_ATTEMPTS", "2"))

if MAX_ATTEMPTS < 1:
    raise ValueError("WEATHER_MAX_ATTEMPTS 必须至少为 1")

RETRY_DELAY_SECONDS = float(
    os.getenv("WEATHER_RETRY_DELAY_SECONDS", "1")
)

if not math.isfinite(RETRY_DELAY_SECONDS) or RETRY_DELAY_SECONDS < 0:
    raise ValueError(
        "WEATHER_RETRY_DELAY_SECONDS 必须是有限数且不小于 0"
    )



logger = logging.getLogger(__name__)


def request_json(
    url: str,
    params: dict,
) -> dict:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=(3, 10),
            )
            response.raise_for_status()
            data = response.json()
            return data

        except requests.Timeout:
            if attempt == MAX_ATTEMPTS:
                raise

            logger.warning(
                "请求超时，准备重试：url=%s，attempt=%s/%s",
                url,
                attempt,
                MAX_ATTEMPTS,
            )
            time.sleep(RETRY_DELAY_SECONDS)

    # MAX_ATTEMPTS 已保证至少为 1；正常情况下循环只会返回或抛出异常。
    raise AssertionError("天气请求循环意外结束")


def search_city(city: str) -> dict:
    params = {
        "name": city,
        "count": 1,
        "language": "zh",
        "format": "json",
    }

    return request_json(
        url=GEOCODING_URL,
        params=params
    )


def get_coordinates(
        city: str,
) -> tuple[float,float] | None:
    data = search_city(city)

    results = data.get("results", [])

    if len(results) == 0:
        return None

    first_result = results[0]
    latitude = first_result["latitude"]
    longitude = first_result["longitude"]

    return latitude,longitude


def fetch_weather(
    latitude: float,
    longitude: float,
    days: int,
) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min",
        "forecast_days": days,
        "timezone": "auto",
    }

    return request_json(
        url=FORECAST_URL,
        params=params,
    )



def format_daily_weather(data: dict) -> list[dict]:
    daily = data["daily"]

    dates = daily["time"]
    max_temperatures = daily["temperature_2m_max"]
    min_temperatures = daily["temperature_2m_min"]

    weather_days: list[dict] = []

    for index in range(len(dates)):
        weather_days.append(
            {
                "date": dates[index],
                "max_temperature": max_temperatures[index],
                "min_temperature": min_temperatures[index],
            }
        )

    return weather_days



def get_weather_forecast(
    city: str,
    days: int,
) -> list[dict]:
    coordinates = get_coordinates(city)

    if coordinates is None:
        raise ValueError("找不到城市")

    latitude, longitude = coordinates

    data = fetch_weather(latitude,longitude,days)

    return format_daily_weather(data)
