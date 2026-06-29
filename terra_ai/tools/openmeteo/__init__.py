"""Open-Meteo weather tools for TerraAI.

Client-side tools backed by the Open-Meteo API (no API key required):
- weather_forecast: current + future weather
- weather_history: past weather by date/range
- air_quality: AQI, PM2.5, ozone, smoke, UV, pollen
- weather_reference: developer/debug inventory of Open-Meteo capabilities

These are LLM-facing function tools. The model decides when to call them;
TerraAI executes them locally and feeds structured results back.
"""

from terra_ai.tools.openmeteo.result import ToolResult

__all__ = ["ToolResult"]
