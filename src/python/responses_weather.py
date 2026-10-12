"""Fictional local weather contract shared by function-calling examples."""

from __future__ import annotations

from typing import Literal, cast

from openai.types.responses.function_tool_param import FunctionToolParam
from pydantic import BaseModel, ConfigDict, Field

WEATHER_TOOL_NAME = "get_weather"


class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: Literal["London", "Seattle", "Sydney", "Tokyo"] = Field(
        description="One fictional fixture location."
    )
    unit: Literal["celsius", "fahrenheit"] = Field(
        description="Temperature unit for the local result.",
    )


class WeatherResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str
    temperature: float
    unit: Literal["celsius", "fahrenheit"]
    conditions: str
    source: Literal["fictional-local-fixture"] = "fictional-local-fixture"


_WEATHER_FIXTURES: dict[str, tuple[float, str]] = {
    "London": (14.0, "light rain"),
    "Seattle": (12.0, "overcast"),
    "Sydney": (24.0, "sunny"),
    "Tokyo": (19.0, "clear"),
}


def weather_tool(*, strict: bool = True) -> FunctionToolParam:
    """Build tool JSON Schema from the same model used for local validation."""
    return {
        "type": "function",
        "name": WEATHER_TOOL_NAME,
        "description": "Look up fictional weather from a local fixture.",
        "parameters": cast(dict[str, object], WeatherArguments.model_json_schema()),
        "strict": strict,
    }


def get_weather(arguments: WeatherArguments) -> WeatherResult:
    temperature_celsius, conditions = _WEATHER_FIXTURES[arguments.location]
    temperature = temperature_celsius
    if arguments.unit == "fahrenheit":
        temperature = round((temperature_celsius * 9 / 5) + 32, 1)

    return WeatherResult(
        location=arguments.location,
        temperature=temperature,
        unit=arguments.unit,
        conditions=conditions,
    )
