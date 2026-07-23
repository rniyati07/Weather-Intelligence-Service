"""Per-provider condition vocabulary → the internal `WeatherCondition` enum.

Each provider has its own coded condition vocabulary; these tables are the
only place that vocabulary is known. An unmapped code falls back to the
closest supported value and logs a `WARNING` — it never crashes the adapter.
"""

import logging

from app.domain.entities.weather import WeatherCondition

logger = logging.getLogger(__name__)

# Open-Meteo: WMO weather interpretation codes ("weathercode").
_OPEN_METEO_MAP: dict[int, WeatherCondition] = {
    0: WeatherCondition.CLEAR,
    1: WeatherCondition.CLEAR,
    2: WeatherCondition.PARTLY_CLOUDY,
    3: WeatherCondition.CLOUDY,
    45: WeatherCondition.FOG,
    48: WeatherCondition.FOG,
    51: WeatherCondition.RAIN,
    53: WeatherCondition.RAIN,
    55: WeatherCondition.RAIN,
    56: WeatherCondition.RAIN,
    57: WeatherCondition.RAIN,
    61: WeatherCondition.RAIN,
    63: WeatherCondition.RAIN,
    65: WeatherCondition.HEAVY_RAIN,
    66: WeatherCondition.RAIN,
    67: WeatherCondition.HEAVY_RAIN,
    71: WeatherCondition.SNOW,
    73: WeatherCondition.SNOW,
    75: WeatherCondition.SNOW,
    77: WeatherCondition.SNOW,
    80: WeatherCondition.RAIN,
    81: WeatherCondition.RAIN,
    82: WeatherCondition.HEAVY_RAIN,
    85: WeatherCondition.SNOW,
    86: WeatherCondition.SNOW,
    95: WeatherCondition.THUNDERSTORM,
    96: WeatherCondition.THUNDERSTORM,
    99: WeatherCondition.THUNDERSTORM,
}

# OpenWeather: numeric condition codes, grouped by leading digit.
_OPENWEATHER_MAP: dict[int, WeatherCondition] = {
    **dict.fromkeys(range(200, 233), WeatherCondition.THUNDERSTORM),
    **dict.fromkeys(range(300, 322), WeatherCondition.RAIN),
    500: WeatherCondition.RAIN,
    501: WeatherCondition.RAIN,
    502: WeatherCondition.HEAVY_RAIN,
    503: WeatherCondition.HEAVY_RAIN,
    504: WeatherCondition.HEAVY_RAIN,
    511: WeatherCondition.HEAVY_RAIN,
    520: WeatherCondition.RAIN,
    521: WeatherCondition.RAIN,
    522: WeatherCondition.HEAVY_RAIN,
    531: WeatherCondition.HEAVY_RAIN,
    **dict.fromkeys(range(600, 623), WeatherCondition.SNOW),
    701: WeatherCondition.FOG,
    711: WeatherCondition.FOG,
    721: WeatherCondition.FOG,
    731: WeatherCondition.FOG,
    741: WeatherCondition.FOG,
    751: WeatherCondition.FOG,
    761: WeatherCondition.FOG,
    762: WeatherCondition.FOG,
    771: WeatherCondition.FOG,
    781: WeatherCondition.FOG,
    800: WeatherCondition.CLEAR,
    801: WeatherCondition.PARTLY_CLOUDY,
    802: WeatherCondition.PARTLY_CLOUDY,
    803: WeatherCondition.CLOUDY,
    804: WeatherCondition.CLOUDY,
}

# WeatherAPI: their documented numeric "condition.code" vocabulary.
_WEATHERAPI_MAP: dict[int, WeatherCondition] = {
    1000: WeatherCondition.CLEAR,
    1003: WeatherCondition.PARTLY_CLOUDY,
    1006: WeatherCondition.CLOUDY,
    1009: WeatherCondition.CLOUDY,
    1030: WeatherCondition.FOG,
    1063: WeatherCondition.RAIN,
    1066: WeatherCondition.SNOW,
    1069: WeatherCondition.SNOW,
    1072: WeatherCondition.RAIN,
    1087: WeatherCondition.THUNDERSTORM,
    1114: WeatherCondition.SNOW,
    1117: WeatherCondition.SNOW,
    1135: WeatherCondition.FOG,
    1147: WeatherCondition.FOG,
    1150: WeatherCondition.RAIN,
    1153: WeatherCondition.RAIN,
    1168: WeatherCondition.RAIN,
    1171: WeatherCondition.HEAVY_RAIN,
    1180: WeatherCondition.RAIN,
    1183: WeatherCondition.RAIN,
    1186: WeatherCondition.RAIN,
    1189: WeatherCondition.RAIN,
    1192: WeatherCondition.HEAVY_RAIN,
    1195: WeatherCondition.HEAVY_RAIN,
    1198: WeatherCondition.RAIN,
    1201: WeatherCondition.HEAVY_RAIN,
    1204: WeatherCondition.SNOW,
    1207: WeatherCondition.SNOW,
    1210: WeatherCondition.SNOW,
    1213: WeatherCondition.SNOW,
    1216: WeatherCondition.SNOW,
    1219: WeatherCondition.SNOW,
    1222: WeatherCondition.SNOW,
    1225: WeatherCondition.SNOW,
    1237: WeatherCondition.SNOW,
    1240: WeatherCondition.RAIN,
    1243: WeatherCondition.HEAVY_RAIN,
    1246: WeatherCondition.HEAVY_RAIN,
    1249: WeatherCondition.SNOW,
    1252: WeatherCondition.SNOW,
    1255: WeatherCondition.SNOW,
    1258: WeatherCondition.SNOW,
    1261: WeatherCondition.SNOW,
    1264: WeatherCondition.SNOW,
    1273: WeatherCondition.THUNDERSTORM,
    1276: WeatherCondition.THUNDERSTORM,
    1279: WeatherCondition.THUNDERSTORM,
    1282: WeatherCondition.THUNDERSTORM,
}

# Severity ranking used when aggregating several sub-daily conditions into
# one daily value (OpenWeather's 3-hourly entries) — highest wins.
CONDITION_SEVERITY: dict[WeatherCondition, int] = {
    WeatherCondition.CLEAR: 0,
    WeatherCondition.PARTLY_CLOUDY: 1,
    WeatherCondition.CLOUDY: 2,
    WeatherCondition.FOG: 3,
    WeatherCondition.RAIN: 4,
    WeatherCondition.SNOW: 5,
    WeatherCondition.HEAVY_RAIN: 6,
    WeatherCondition.THUNDERSTORM: 7,
}


def _map_or_fallback(
    code: int, table: dict[int, WeatherCondition], *, provider: str
) -> WeatherCondition:
    condition = table.get(code)
    if condition is not None:
        return condition
    logger.warning("provider_unmapped_condition_code", extra={"provider": provider, "code": code})
    return WeatherCondition.CLOUDY  # closest neutral default when a code is unrecognized


def map_open_meteo_condition(weather_code: int) -> WeatherCondition:
    return _map_or_fallback(weather_code, _OPEN_METEO_MAP, provider="open_meteo")


def map_openweather_condition(condition_id: int) -> WeatherCondition:
    return _map_or_fallback(condition_id, _OPENWEATHER_MAP, provider="openweather")


def map_weatherapi_condition(condition_code: int) -> WeatherCondition:
    return _map_or_fallback(condition_code, _WEATHERAPI_MAP, provider="weatherapi")
