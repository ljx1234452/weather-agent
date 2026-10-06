import os
from pathlib import Path
from openai import OpenAI
import json
from dotenv import load_dotenv
from 天气.tool_schemas import get_weather_tool_schema
from 天气.handler import handle_tool_call
from 天气.results import ToolResult
from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionMessageParam,
)
from typing import cast


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class ModelConfigurationError(Exception):
    """模型连接所需的环境变量尚未配置。"""


client: OpenAI | None = None


def get_client() -> OpenAI:
    global client
    if client is None:
        api_key = os.environ.get("MODEL_API_KEY")
        base_url = os.environ.get("MODEL_BASE_URL")
        missing = [
            name
            for name, value in (
                ("MODEL_API_KEY", api_key),
                ("MODEL_BASE_URL", base_url),
            )
            if not value
        ]
        if missing:
            raise ModelConfigurationError(
                f"缺少模型配置：{', '.join(missing)}"
            )
        client = OpenAI(
            api_key=cast(str, api_key),
            base_url=cast(str, base_url),
        )
    return client

SYSTEM_MESSAGE: ChatCompletionMessageParam = {
    "role": "system",
    "content": (
        "你是一个天气查询助手。"
        "回答要简洁、准确。"
        "用户询问真实天气时必须调用天气工具，不要自己编造天气数据。"
    ),
}


def ask_model(
        user_message: str,
        history: list[ChatCompletionMessageParam],
        ) -> ChatCompletionMessage:
    messages: list[ChatCompletionMessageParam] = [
    SYSTEM_MESSAGE,
    *history,
    {
        "role": "user",
        "content": user_message,
    },
]

    response = get_client().chat.completions.create(
        model=os.environ.get("MODEL_NAME", "gemini-3-flash-c"),
        messages=messages,
        tools=[get_weather_tool_schema()],

    )

    return response.choices[0].message


def ask_model_to_fix_call(
    user_message: str,
    raw_call: dict,
    error_message: str,
) -> ChatCompletionMessage:
    correction_messages: list[ChatCompletionMessageParam] = [
        SYSTEM_MESSAGE,
        {
            "role": "user",
            "content": (
                f"用户原来的问题：{user_message}\n"
                f"上一次工具调用："
                f"{json.dumps(raw_call, ensure_ascii=False)}\n"
                f"参数验证错误：{error_message}\n"
                "请修正参数，并重新调用天气工具。"
            ),
        },
    ]

    response = get_client().chat.completions.create(
        model=os.environ.get("MODEL_NAME", "gemini-3-flash-c"),
        messages=correction_messages,
        tools=[get_weather_tool_schema()],
    )

    return response.choices[0].message



def extract_raw_call(
    message: ChatCompletionMessage,
) -> dict | None:
    if not message.tool_calls:
        return None

    tool_call = message.tool_calls[0]

    if tool_call.type != "function":
        return None

    arguments = json.loads(
        tool_call.function.arguments
    )

    return {
        "tool_name": tool_call.function.name,
        "arguments": arguments,
    }



def run_agent(
    user_message: str,
    history: list[ChatCompletionMessageParam],
    *,
    debug: bool = False,
) -> str:
    conversation: list[ChatCompletionMessageParam] = [
        SYSTEM_MESSAGE,
        *history,
        {
            "role": "user",
            "content": user_message,
        },
    ]

    max_steps = 5

    for _ in range(max_steps):
        response = get_client().chat.completions.create(
            model=os.environ.get(
                "MODEL_NAME",
                "gemini-3-flash-c",
            ),
            messages=conversation,
            tools=[get_weather_tool_schema()],
        )

        message = response.choices[0].message

        # 没有工具调用，说明模型已经给出最终回答
        if not message.tool_calls:
            return message.content or "模型没有生成回答"

        # 保存模型刚才提出的工具调用
        assistant_message = cast(
            ChatCompletionMessageParam,
            message.model_dump(exclude_none=True),
        )
        conversation.append(assistant_message)

        # 执行这一轮的所有工具调用
        for tool_call in message.tool_calls:
            if tool_call.type != "function":
                return "模型请求了不支持的工具类型"

            if debug:
                print(f"模型请求工具：{tool_call.function.name}")

            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = None

            if not isinstance(arguments, dict):
                result = ToolResult(
                    status="error",
                    error_type="validation",
                    error="工具参数必须是有效的 JSON 对象，请重新调用工具",
                )
            else:
                result = handle_tool_call({
                    "tool_name": tool_call.function.name,
                    "arguments": arguments,
                })

            if debug:
                print(f"工具执行状态：{result.status}")

            # 网络错误或工具错误无法靠修改参数解决
            if (
                result.status == "error"
                and result.error_type != "validation"
            ):
                return result.error or "工具执行失败"

            # 成功结果或参数错误都交给下一轮模型
            conversation.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result.model_dump_json(),
            })

    return "Agent 执行步骤过多，已经停止"



if __name__ == "__main__":
    user_message = "你好，请简单介绍一下自己"
    history: list[ChatCompletionMessageParam] = []
    answer = run_agent(user_message, history)
    print(answer)
