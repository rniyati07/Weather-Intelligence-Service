# `components/cards`

**Empty, and deliberately so.**

This folder was reserved in the foundation phase on the assumption that the
verdict cards, timeline cards and AI panel would be shared. They are not: every
one of them is consumed by the dashboard alone, so under the project's
extraction rule — promote only when a second consumer actually exists — they
live in `features/dashboard/components/`.

What *did* meet the bar went to `components/weather/`:

| Component | Consumers |
|---|---|
| `WeatherIcon` | timeline card, day detail, raw-readings table |
| `AdvisoryChip` | timeline card, day detail |
| `RiskBadge` | landing recent-searches, day detail |
| `DomainIcon` | every enum-driven icon in the app |

Promote a dashboard card here the moment a second feature needs it — a
share/print view of the packing list and a compact verdict widget are the two
likeliest candidates. Until then, moving them here would buy indirection and
nothing else.
