from 天气.handler import handle_tool_call
from 天气.results import ToolResult
import json



def handle_model_response(
        model_response: dict,
) -> ToolResult | str:
    if model_response["type"] == "tool_call":
        raw_call ={
            "tool_name": model_response["tool_name"],
            "arguments": model_response["arguments"],
        }

        return handle_tool_call(raw_call)

    return model_response["content"]



def execute_function_call(
        function_call:dict,
) -> dict:
    arguments = json.loads(function_call["arguments"]
                           )
    raw_call ={
        "tool_name": function_call["name"],
        "arguments": arguments,
    }

    tool_result = handle_tool_call(raw_call)

    return {
        "type": "function_call_output",
        "call_id": function_call["call_id"],
        "output": tool_result.model_dump_json(),
    }



if __name__ == "__main__":
    function_call = {
        "type": "function_call",
        "name": "weather",
        "arguments": '{"city":"Guangzhou","days":10}',
        "call_id": "call_123",
    }

    function_call_output = execute_function_call(
        function_call
    )

    print(json.dumps(
        function_call_output,
        ensure_ascii=False,
        indent=2,
    ))