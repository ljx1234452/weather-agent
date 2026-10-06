from pydantic import ValidationError


def format_validation_error(error: ValidationError) -> str:

    messages = []

    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        reason = item["msg"]
        input_value = item["input"]

        messages.append(f"字段 '{location}' 的值 '{input_value}' 不正确: {reason}")

    return "\n".join(messages)