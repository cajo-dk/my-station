# My Station Card

Compact Lovelace card for the `items` attribute exposed by the My Station sensor.

The integration bundles this file at `/my_station/my-station-card.js` and
automatically registers it as a dashboard resource in storage mode. YAML-managed
resource lists must add that URL manually as a JavaScript module. Then use:

```yaml
type: custom:my-station-card
entity: sensor.my_station_departures
title: Herfølge St. - Departures
max_rows: 8
show_status: true
show_updated: true
```

`max_rows` accepts 1-100. Both `show_status` and `show_updated` are optional.
