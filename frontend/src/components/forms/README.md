# `components/forms`

**Empty.** Reserved for form controls that are genuinely shared.

`DateRangePicker` was originally placed here on the expectation that the
dashboard's "Edit dates" control would open the same picker. It does not — that
control links back to `/plan` — so the picker had exactly one consumer and
encodes domain rules of its own (the 16-day forecast horizon, its copy, and the
`forecastBounds` selection logic). It now lives in
`features/planner/components/DateRangePicker.tsx`.

Promote it here the moment a second feature opens a date picker. Nothing else
about it would need to change: it already takes `value` / `onChange` / `months`
and renders no layout of its own, precisely so the caller decides presentation.

The two forms in the product — destination search and date selection — are both
owned by the planner. A control only belongs here once that stops being true.
