from typing import Literal

from pydantic import BaseModel


class ToolResult(BaseModel):
    status: Literal["success","error"]
    data: dict | None = None
    error_type: Literal["validation", "network", "tool"] | None = None
    error: str | None = None
