# My Station Card

Compact Lovelace card for the `items` attribute exposed by the My Station sensor.

The integration bundles this file at `/my_station/my-station-card.js`. Add that URL as a JavaScript module under **Settings -> Dashboards -> Resources**, then use:

```yaml
type: custom:my-station-card
entity: sensor.my_station_departures
title: Herfølge St. - Departures
max_rows: 8
show_status: true
show_updated: true
```

`max_rows` accepts 1-100. Both `show_status` and `show_updated` are optional.
