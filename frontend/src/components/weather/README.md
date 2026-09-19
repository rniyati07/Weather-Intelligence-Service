# `components/weather`

Weather-specific display primitives — reserved, empty in the foundation phase.

The small, repeated pieces that render one weather value each. They sit below
`components/cards` in granularity: a card composes several of these.

Planned occupants:

| Component | Purpose |
|---|---|
| `WeatherIcon` | `WeatherCondition` → icon. Unknown value → neutral cloud, never a crash. |
| `RiskBadge` | Risk level as icon + text + colour. |
| `AdvisoryChip` | `proceed` / `caution` / `avoid`. |
| `TemperatureDisplay` | Honours the °C/°F preference; tabular numerals. |
| `PrecipitationIndicator` | `0.0–1.0` rendered as a percentage. |
| `WindIndicator` | Emphasised when a `wind` risk factor fired. |
| `ActivityBars` | Renders whatever categories arrive; never hardcodes the v1 three. |

Every icon that conveys meaning carries an accessible label, or is
`aria-hidden` with the meaning carried by adjacent text (FDS §14.3). Nothing
here decides anything — the enum-to-presentation maps live in
`constants/domain.ts` and are read through `utils/domain.ts`.
