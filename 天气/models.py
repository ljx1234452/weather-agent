from pydantic import BaseModel,ConfigDict,Field
from typing import Literal



class SearchInput(BaseModel):
    keyword: str
    limit: int = Field(ge=1,le=10)

class SearchToolCall(BaseModel):
    tool_name: Literal["search"]
    arguments: SearchInput

class WeatherInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(
        description=(
        "城市的英文名称。"
        "如果用户输入中文城市名，调用工具前转换成英文，"
        "例如：广州转换为 Guangzhou，肇庆转换为 Zhaoqing。"
))
    days: int = Field(ge=1,le=7, description="需要查询的天气天数，范围为1到7天。")

class WeatherToolCall(BaseModel):
    tool_name: Literal["weather"]
    arguments: WeatherInput

ToolCall = SearchToolCall | WeatherToolCall
