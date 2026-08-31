# My Station

My Station is a Home Assistant custom integration for Rejseplanen departure boards. It calls Rejseplanen directly, polls through Home Assistant's `DataUpdateCoordinator`, exposes a compact sensor payload, and includes the `custom:my-station-card` Lovelace card.

It replaces the standalone `rejseplanen` add-on/MQTT path. The compact response and the original rail filter (`ProductAtStop.catOut == "Re"`) retain the existing app's behavior, including delay, cancellation, partial-cancellation, changed-destination, and service-message fields.

## Requirements

- Home Assistant 2024.7 or newer
- HACS (recommended for installation)
- A Rejseplanen API access ID. Access is requested through [Rejseplanen Labs](https://labs.rejseplanen.dk/hc/da/articles/21553113674909-Adgang-til-data-fra-Labs).
- A Rejseplanen station/stop ID, such as `8600626`

The API owner applies usage quotas. Choose a polling interval appropriate for your account and number of configured stations.

## Install with HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add `https://github.com/cajo-dk/my-station` with category **Integration**.
4. Find **My Station**, select **Download**, and restart Home Assistant.
5. Go to **Settings -> Devices & services -> Add integration**, search for **My Station**, and complete the form.

HACS installs everything needed at runtime from `custom_components/my_station`, including the packaged card file.

## Manual installation

Copy `custom_components/my_station` into the `custom_components` directory in your Home Assistant configuration, then restart Home Assistant. The resulting path must be:

```text
<config>/custom_components/my_station/manifest.json
```

## Configure the integration

All setup fields are required. The setup flow verifies the credentials and station by making a live read-only departure-board request before it creates the entry.

| Setting | Default | Allowed | Purpose |
| --- | ---: | ---: | --- |
| Name | My Station | non-empty text | Device/config-entry display name |
| Access ID | none | non-empty text | Rejseplanen API credential |
| Station/stop ID | `8600626` | non-empty text | Departure-board location |
| Maximum journeys | 80 | 1-500 | Maximum API results |
| Departure window | 60 minutes | 1-1440 | How far ahead to request |
| Update interval | 60 minutes | 1-1440 | Coordinator polling interval |

To change the result size, departure window, or polling interval later, open the integration entry and select **Configure**. To change the API access ID or station/stop ID, select **Reconfigure** from the integration entry's menu. Leave the API key blank during reconfiguration to retain its current value. Authentication failures start Home Assistant's reauthentication flow; other request failures mark the sensor unavailable while the coordinator retries normally.

One integration instance is allowed per station/stop ID.

## Sensor payload

Each config entry creates one sensor. Its state is the number of compact departures. The attributes contain the compact payload formerly published over MQTT:

```yaml
count: 2
updated: "2026-08-31T09:00:00+02:00"
ok: true
error: null
items:
  - trainId: Re 1234
    direction: København H
    scheduledDirection: København H
    actualDirection: København H
    destinationChanged: false
    cancelledBetweenFrom: null
    cancelledBetweenTo: null
    partCancelled: false
    serviceMessage: null
    departs: Herfølge St.
    plannedDate: "2026-08-31"
    plannedTime: "09:10:00"
    actualDate: "2026-08-31"
    actualTime: "09:13:00"
    status: delayed
```

The exact entity ID is assigned by Home Assistant and can be copied from the integration's entity page.

## Add the Lovelace card

After the integration has been configured, add its bundled JavaScript file as a dashboard resource:

1. Go to **Settings -> Dashboards**.
2. Open the three-dot menu, then **Resources**.
3. Add `/my_station/my-station-card.js` as a **JavaScript module**.
4. Refresh the browser.

Add the card in YAML mode:

```yaml
type: custom:my-station-card
entity: sensor.my_station_departures
title: Herfølge St. - Departures
icon: mdi:train
icon_size: 30
max_rows: 8
show_status: true
show_updated: true
```

Card options:

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `entity` | yes | none | My Station sensor entity ID |
| `title` | no | Departures | Card heading; use an empty string to hide it |
| `icon` | no | `mdi:train` | Icon shown to the left of the title; use an empty string to hide it |
| `icon_size` | no | 30 | Icon size in pixels, from 1 to 100 |
| `max_rows` | no | 8 | Rows to display, from 1 to 100 |
| `show_status` | no | `true` | Show the status badge column |
| `show_updated` | no | `true` | Show the payload update time |

When Rejseplanen supplies a service message for a departure, the card displays it
on a full-width line directly below that departure.

The development source lives at `custom_cards/my-station-card/my-station-card.js`. An identical copy is packaged at `custom_components/my_station/frontend/my-station-card.js` because HACS integration repositories install runtime files from the integration directory.

## Development validation

Before publishing a release, run:

```powershell
python -m compileall -q custom_components
node --check custom_cards/my-station-card/my-station-card.js
```

The repository includes HACS and hassfest GitHub Actions. Publish a GitHub release (for example `v1.0.0`) so HACS can present versioned downloads.

## Support

Report integration or card issues at [cajo-dk/my-station](https://github.com/cajo-dk/my-station/issues). API availability, credentials, quotas, and source data are controlled by Rejseplanen.

## License

MIT
