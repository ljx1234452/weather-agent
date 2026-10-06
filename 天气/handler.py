from pydantic import ValidationError
import requests
from 天气.dispatcher import execute_tool_call, parse_tool_call
from 天气.results import ToolResult
from 天气.agent_errors import format_validation_error
import logging


logger = logging.getLogger(__name__)

def handle_tool_call(raw_call: dict) -> ToolResult:
    try:
        tool_call = parse_tool_call(raw_call)
        data = execute_tool_call(tool_call)

        return ToolResult(
            status="success",
            data=data
        )

    except requests.Timeout:
        logger.warning("天气服务请求超时")

        return ToolResult(
            status="error",
            error="天气服务响应超时，请稍后重试",
            error_type="network",
        )

    except requests.HTTPError as error:
        logger.warning("天气服务返回错误状态：%s", error)

        if error.response is not None and error.response.status_code == 429:
            return ToolResult(
                status="error",
                error="天气查询过于频繁，请稍后再试",
                error_type="network",
            )

        return ToolResult(
            status="error",
            error="天气服务暂时不可用，请稍后重试",
            error_type="network",
        )

    except ValidationError as error:
        return ToolResult(
        status="error",
        error_type="validation",
        error=format_validation_error(error),
    )

    except ValueError as error:
        return ToolResult(
        status="error",
        error_type="tool",
        error=str(error),
    )


    except requests.RequestException:
        return ToolResult(
            status="error",
            error="天气服务请求失败，请稍后重试",
            error_type="network",
        )