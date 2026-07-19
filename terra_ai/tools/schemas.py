"""Provider-neutral local function-tool schemas for TerraAI."""

from terra_ai.tools.openmeteo.schemas import (
    WEATHER_FORECAST_TOOL,
)

# weather_forecast geocodes internally, so a standalone geocode tool is not
# exposed. Provider-native tools belong to their provider adapter.
LOCAL_TOOLS = [
    WEATHER_FORECAST_TOOL,
]
