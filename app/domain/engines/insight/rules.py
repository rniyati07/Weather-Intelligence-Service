"""Pure predicates: `NormalizedReading` + `RuleConfig` -> triggered rules.

Every rule id is stable (e.g. `precip_prob_gt_0_6`) and carries its
`RiskFactorType` and `Severity` — this is what satisfies explainability
(NFR-1): every `RiskFactor` the risk engine emits traces back to exactly the
rule that fired it. No I/O, no clock, no randomness — a pure function of its
two inputs.
"""

from dataclasses import dataclass

from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.rules.config import RiskFactorType, RuleConfig, Severity

#: Every rule id this module can ever produce — the closed catalog that
#: rule-config thresholds parameterize. The explainability test asserts
#: every emitted `RiskFactor.rule` is a member of this set: "traceable to
#: the rule config" means traceable to exactly one of these, whose
#: threshold values live in `RuleConfig`.
KNOWN_RULE_IDS = frozenset(
    {
        "temp_max_gt_moderate",
        "temp_max_gt_high",
        "temp_min_lt_moderate",
        "temp_min_lt_high",
        "precip_prob_gt_0_6",
        "precip_prob_gt_high",
        "wind_speed_gt_moderate",
        "wind_speed_gt_high",
        "condition_is_thunderstorm",
        "condition_is_heavy_rain",
    }
)


@dataclass(frozen=True, slots=True)
class TriggeredRule:
    """One fired rule: its stable id, the risk category it belongs to, and why."""

    rule_id: str
    factor_type: RiskFactorType
    severity: Severity
    description: str


def evaluate(reading: NormalizedReading, config: RuleConfig) -> list[TriggeredRule]:
    """Return every rule that fires for `reading`.

    Each risk category evaluates independently — a day can trigger heat,
    rain, wind, *and* storm rules simultaneously. Within a category, only the
    single highest tier that clears its threshold fires (a "high" reading
    doesn't also separately trigger "moderate").
    """
    thresholds = config.insight_thresholds
    triggered: list[TriggeredRule] = []

    if reading.temp_max_c > thresholds.heat.high_temp_max_c:
        triggered.append(
            TriggeredRule(
                "temp_max_gt_high",
                "heat",
                "high",
                f"Daytime high of {reading.temp_max_c:.1f}°C exceeds the high-heat threshold "
                f"({thresholds.heat.high_temp_max_c:.1f}°C).",
            )
        )
    elif reading.temp_max_c > thresholds.heat.moderate_temp_max_c:
        triggered.append(
            TriggeredRule(
                "temp_max_gt_moderate",
                "heat",
                "moderate",
                f"Daytime high of {reading.temp_max_c:.1f}°C exceeds the moderate-heat "
                f"threshold ({thresholds.heat.moderate_temp_max_c:.1f}°C).",
            )
        )

    if reading.temp_min_c < thresholds.cold.high_temp_min_c:
        triggered.append(
            TriggeredRule(
                "temp_min_lt_high",
                "cold",
                "high",
                f"Overnight low of {reading.temp_min_c:.1f}°C is below the high-cold "
                f"threshold ({thresholds.cold.high_temp_min_c:.1f}°C).",
            )
        )
    elif reading.temp_min_c < thresholds.cold.moderate_temp_min_c:
        triggered.append(
            TriggeredRule(
                "temp_min_lt_moderate",
                "cold",
                "moderate",
                f"Overnight low of {reading.temp_min_c:.1f}°C is below the moderate-cold "
                f"threshold ({thresholds.cold.moderate_temp_min_c:.1f}°C).",
            )
        )

    if reading.precipitation_probability > thresholds.rain.high_precip_probability:
        triggered.append(
            TriggeredRule(
                "precip_prob_gt_high",
                "rain",
                "high",
                f"{reading.precipitation_probability:.0%} chance of precipitation exceeds the "
                f"high-rain threshold ({thresholds.rain.high_precip_probability:.0%}).",
            )
        )
    elif reading.precipitation_probability > thresholds.rain.moderate_precip_probability:
        triggered.append(
            TriggeredRule(
                "precip_prob_gt_0_6",
                "rain",
                "moderate",
                f"{reading.precipitation_probability:.0%} chance of precipitation exceeds the "
                f"moderate-rain threshold ({thresholds.rain.moderate_precip_probability:.0%}).",
            )
        )

    if reading.wind_speed_kph > thresholds.wind.high_wind_speed_kph:
        triggered.append(
            TriggeredRule(
                "wind_speed_gt_high",
                "wind",
                "high",
                f"Wind speed of {reading.wind_speed_kph:.0f} km/h exceeds the high-wind "
                f"threshold ({thresholds.wind.high_wind_speed_kph:.0f} km/h).",
            )
        )
    elif reading.wind_speed_kph > thresholds.wind.moderate_wind_speed_kph:
        triggered.append(
            TriggeredRule(
                "wind_speed_gt_moderate",
                "wind",
                "moderate",
                f"Wind speed of {reading.wind_speed_kph:.0f} km/h exceeds the moderate-wind "
                f"threshold ({thresholds.wind.moderate_wind_speed_kph:.0f} km/h).",
            )
        )

    if reading.condition == WeatherCondition.THUNDERSTORM:
        triggered.append(
            TriggeredRule(
                "condition_is_thunderstorm", "storm", "high", "Thunderstorms are expected."
            )
        )
    elif reading.condition == WeatherCondition.HEAVY_RAIN:
        triggered.append(
            TriggeredRule(
                "condition_is_heavy_rain", "storm", "moderate", "Heavy rain is expected."
            )
        )

    return triggered
