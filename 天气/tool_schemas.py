import json

from openai.types.chat import ChatCompletionToolParam

from 天气.models import WeatherInput



def get_weather_tool_schema() -> ChatCompletionToolParam:
    return {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "查询指定城市未来几天的天气",
            "parameters": WeatherInput.model_json_schema(),
            "strict": True,
        },
    }

if __name__ == "__main__":
    schema = get_weather_tool_schema()
    print(json.dumps(
    schema,
    ensure_ascii=False,
    indent=2,
))
