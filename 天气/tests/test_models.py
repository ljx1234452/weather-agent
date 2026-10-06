from 天气.models import WeatherInput,SearchInput
import pytest
from pydantic import ValidationError
from 天气.tool_schemas import get_weather_tool_schema



@pytest.mark.parametrize("days",[0,8])
def test_weather_days_out_of_range(days:int):
    with pytest.raises(ValidationError):
        WeatherInput(
            city="Guangzhou",
            days=days,
        )



@pytest.mark.parametrize("city,days",[("Guangzhou",1),("Shenzhen",7)])
def test_weather_days_valid_boundaries(city: str,days: int):
    weather_input=WeatherInput(
        city=city,
        days=days,
    )

    assert weather_input.city == city
    assert weather_input.days == days



@pytest.mark.parametrize("limit",[1,10])
def test_search_limit_valid_boundaries(limit:int):
    search_input=SearchInput(
        keyword="Python Agent",
        limit=limit
    )

    assert search_input.limit == limit


@pytest.mark.parametrize("limit", [0, 11])
def test_search_limit_out_of_range(limit: int):
    with pytest.raises(ValidationError):
        SearchInput(
            keyword="Python Agent",
            limit=limit
        )



def test_shared_weather_fixture(
    weather_input: WeatherInput,
):
    assert weather_input.city == "Guangzhou"
    assert weather_input.days == 3


def test_weather_schema_supports_strict_tool_calls():
    schema = get_weather_tool_schema()["function"]["parameters"]

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
