from http.client import FORBIDDEN
from unittest.mock import Mock

from 天气.api_client import (
    FORECAST_URL,
    format_daily_weather,
    get_coordinates,
    search_city,
    GEOCODING_URL,
    FORECAST_URL,
    fetch_weather,
    RETRY_DELAY_SECONDS,
)
import pytest
import requests



@pytest.fixture(autouse=True)
def mock_retry_sleep(monkeypatch):
    mock_sleep = Mock(return_value=None)

    monkeypatch.setattr(
        "天气.api_client.time.sleep",
        mock_sleep,
    )

    return mock_sleep


def test_format_daily_weather():
    raw_data = {
        "daily": {
            "time": [
                "2026-08-27",
                "2026-08-28",
            ],
            "temperature_2m_max": [
                31.0,
                32.0,
            ],
            "temperature_2m_min": [
                25.0,
                26.0,
            ],
        }
    }

    result = format_daily_weather(raw_data)

    assert result == [
        {
            "date": "2026-08-27",
            "max_temperature": 31.0,
            "min_temperature": 25.0,
        },
        {
            "date": "2026-08-28",
            "max_temperature": 32.0,
            "min_temperature": 26.0,
        },
    ]




def test_format_daily_weather_with_empty_data():
    raw_data = {
        "daily": {
            "time": [],
            "temperature_2m_max": [],
            "temperature_2m_min": [],
        }
    }

    result = format_daily_weather(raw_data)

    assert result == []


def test_get_coordinates(
    monkeypatch,
):
    fake_city_data = {
        "results": [
            {
                "name": "广州",
                "latitude": 23.11667,
                "longitude": 113.25,
            }
        ]
    }

    mock_search_city = Mock(
        return_value=fake_city_data
    )

    monkeypatch.setattr(
        "天气.api_client.search_city",
        mock_search_city
    )

    result = get_coordinates("Guangzhou")

    assert result == (23.11667, 113.25)

    mock_search_city.assert_called_once_with(
        "Guangzhou"
    )



def test_get_coordinates_returns_none_when_city_not_found(
    monkeypatch,
):
    fake_city_data = {
        "results":[]
    }

    mock_search_city = Mock(
        return_value=fake_city_data
    )

    monkeypatch.setattr(
        "天气.api_client.search_city",
                mock_search_city
    )

    result = get_coordinates("UnknownCity")

    assert result is None

    mock_search_city.assert_called_once_with(
            "UnknownCity"
        )



def test_search_city(
    monkeypatch,
    mock_retry_sleep,
):
    fake_city_data = {
        "results": [
            {
                "name": "广州",
                "latitude": 23.11667,
                "longitude": 113.25,
            }
        ]
    }

    mock_response = Mock()
    mock_response.json.return_value = fake_city_data

    mock_get = Mock(
        return_value=mock_response
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    result = search_city("Guangzhou")

    assert result == fake_city_data
    mock_response.raise_for_status.assert_called_once_with()
    mock_response.json.assert_called_once_with()
    mock_get.assert_called_once_with(
    GEOCODING_URL,
    params={
        "name": "Guangzhou",
        "count": 1,
        "language": "zh",
        "format": "json",
    },
    timeout=(3,10),
)
    mock_retry_sleep.assert_not_called()


def test_fetch_weather(
        monkeypatch,
):
    fake_weather_data = {
        "daily":{
            "time": ["2026-08-27"],
            "temperature_2m_max": [31.0],
            "temperature_2m_min": [25.0],
        }
    }

    mock_response = Mock()
    mock_response.json.return_value = fake_weather_data
    mock_get = Mock(
        return_value=mock_response
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    result = fetch_weather(
        latitude=23.11667,
        longitude=113.25,
        days=3,
    )
    assert result == fake_weather_data

    mock_response.raise_for_status.assert_called_once_with()
    mock_response.json.assert_called_once_with()

    mock_get.assert_called_once_with(
        FORECAST_URL,
        params={
            "latitude": 23.11667,
            "longitude": 113.25,
            "daily": "temperature_2m_max,temperature_2m_min",
            "forecast_days": 3,
            "timezone": "auto",
        },
        timeout=(3,10),
    )



def test_search_city_raises_http_error(
    monkeypatch,
):
    mock_response = Mock()

    mock_response.raise_for_status.side_effect = (
        requests.HTTPError("404 Not Found")
    )

    mock_get = Mock(
        return_value=mock_response
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    with pytest.raises(
        requests.HTTPError,
        match="404 Not Found",
    ):
        search_city("Guangzhou")

    mock_response.raise_for_status.assert_called_once_with()
    mock_response.json.assert_not_called()



def test_fetch_weather_raises_http_error(
    monkeypatch,
):
    mock_response = Mock()

    mock_response.raise_for_status.side_effect = (
        requests.HTTPError("天气服务错误")
    )

    mock_get = Mock(
        return_value=mock_response
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    with pytest.raises(
        requests.HTTPError,
        match="天气服务错误"
    ):
        fetch_weather(
            latitude=23.11667,
            longitude=113.25,
            days=3,
        )

    mock_response.raise_for_status.assert_called_once_with()
    mock_response.json.assert_not_called()




def test_fetch_weather_raises_timeout(
    monkeypatch,
    mock_retry_sleep,
):
    mock_get = Mock(
        side_effect=requests.Timeout("请求超时")
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    with pytest.raises(
        requests.Timeout,
        match="请求超时",
    ):
        fetch_weather(
            latitude=23.11667,
            longitude=113.25,
            days=3,
        )

    assert mock_get.call_count == 2

    mock_get.assert_called_with(
        FORECAST_URL,
        params={
            "latitude": 23.11667,
            "longitude": 113.25,
            "daily": "temperature_2m_max,temperature_2m_min",
            "forecast_days": 3,
            "timezone": "auto",
        },
        timeout=(3, 10),
    )
    mock_retry_sleep.assert_called_once_with(RETRY_DELAY_SECONDS)



def test_fetch_weather_succeeds_after_timeout(monkeypatch):
    fake_weather_data = {
        "daily": {
            "time": ["2026-09-29"],
            "temperature_2m_max": [35.0],
            "temperature_2m_min": [27.0],
        }
    }

    mock_response = Mock()
    mock_response.json.return_value = fake_weather_data

    mock_get = Mock(
        side_effect=[
            requests.Timeout("第一次请求超时"),
            mock_response,
        ]
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    result = fetch_weather(
        latitude=23.11667,
        longitude=113.25,
        days=1,
    )

    assert result == fake_weather_data
    assert mock_get.call_count == 2
    mock_response.raise_for_status.assert_called_once_with()
    mock_response.json.assert_called_once_with()


def test_search_city_raises_timeout(
    monkeypatch,
    mock_retry_sleep,
):
    mock_get = Mock(
        side_effect=requests.Timeout("请求超时")
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    with pytest.raises(
        requests.Timeout,
        match="请求超时",
    ):
        search_city("Guangzhou")

    assert mock_get.call_count == 2

    mock_get.assert_called_with(
        GEOCODING_URL,
        params={
            "name": "Guangzhou",
            "count": 1,
            "language": "zh",
            "format": "json",
        },
        timeout=(3, 10),
    )
    mock_retry_sleep.assert_called_once_with(RETRY_DELAY_SECONDS)


def test_search_city_succeeds_after_timeout(
    monkeypatch,
    mock_retry_sleep,
):
    fake_city_data = {
        "results": [
            {
                "name": "广州",
                "latitude": 23.11667,
                "longitude": 113.25,
            }
        ]
    }

    mock_response = Mock()
    mock_response.json.return_value = fake_city_data

    mock_get = Mock(
        side_effect=[
            requests.Timeout("第一次请求超时"),
            mock_response,
        ]
    )

    monkeypatch.setattr(
        "天气.api_client.requests.get",
        mock_get,
    )

    result = search_city("Guangzhou")

    assert result == fake_city_data
    assert mock_get.call_count == 2
    mock_response.raise_for_status.assert_called_once_with()
    mock_response.json.assert_called_once_with()
    mock_retry_sleep.assert_called_once_with(RETRY_DELAY_SECONDS)
