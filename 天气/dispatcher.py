from 天气.models import(
    SearchToolCall,
    WeatherToolCall,
    ToolCall,
)

from 天气.tools import run_search,run_weather


def execute_tool_call(tool_call: ToolCall) -> dict:
    if isinstance(tool_call, SearchToolCall):
        return run_search(tool_call.arguments)

    if isinstance(tool_call, WeatherToolCall):
        return run_weather(tool_call.arguments)

    raise ValueError("不支持的工具")


def parse_tool_call(raw_call: dict) -> ToolCall:
    tool_name = raw_call.get("tool_name")

    if tool_name == "search":
        return SearchToolCall.model_validate(raw_call)

    if tool_name == "weather":
        return WeatherToolCall.model_validate(raw_call)


    raise ValueError("不支持的工具")
