class MyStationCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = undefined;
    this._hass = undefined;
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass?.states || {}).find(
      (entityId) =>
        entityId.startsWith("sensor.") &&
        Array.isArray(hass.states[entityId]?.attributes?.items)
    );
    return { entity: entity || "", title: "Departures", max_rows: 8 };
  }

  setConfig(config) {
    if (!config || typeof config.entity !== "string" || !config.entity.trim()) {
      throw new Error("my-station-card requires a sensor entity");
    }

    const maxRows = Number(config.max_rows ?? 8);
    if (!Number.isInteger(maxRows) || maxRows < 1 || maxRows > 100) {
      throw new Error("max_rows must be an integer from 1 to 100");
    }

    this._config = {
      title: "Departures",
      show_status: true,
      show_updated: true,
      ...config,
      entity: config.entity.trim(),
      max_rows: maxRows,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    const count = this._departureItems().length;
    return Math.max(2, Math.min(count, this._config?.max_rows || 8) + 1);
  }

  _departureItems() {
    if (!this._hass || !this._config) {
      return [];
    }
    const state = this._hass.states[this._config.entity];
    return Array.isArray(state?.attributes?.items) ? state.attributes.items : [];
  }

  _labels() {
    const danish = String(this._hass?.language || "").toLowerCase().startsWith("da");
    return danish
      ? {
          time: "Tid",
          train: "Tog",
          direction: "Destination",
          status: "Status",
          delayed: "Forsinket",
          cancelled: "Aflyst",
          on_time: "Til tiden",
          unavailable: "Sensoren er ikke tilgængelig",
          empty: "Ingen afgange",
          updated: "Opdateret",
        }
      : {
          time: "Time",
          train: "Train",
          direction: "Direction",
          status: "Status",
          delayed: "Delayed",
          cancelled: "Cancelled",
          on_time: "On time",
          unavailable: "Sensor is unavailable",
          empty: "No departures",
          updated: "Updated",
        };
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const labels = this._labels();
    const state = this._hass?.states?.[this._config.entity];
    const card = document.createElement("ha-card");
    const wrapper = document.createElement("div");
    wrapper.className = "wrapper";

    if (this._config.title) {
      const header = document.createElement("div");
      header.className = "card-header";
      header.textContent = this._config.title;
      wrapper.append(header);
    }

    if (!state || state.state === "unavailable" || state.state === "unknown") {
      wrapper.append(this._message(labels.unavailable));
    } else {
      const items = this._departureItems().slice(0, this._config.max_rows);
      if (items.length === 0) {
        wrapper.append(this._message(labels.empty));
      } else {
        wrapper.append(this._table(items, labels));
      }

      if (this._config.show_updated && state.attributes.updated) {
        const footer = document.createElement("div");
        footer.className = "footer";
        const date = new Date(state.attributes.updated);
        const value = Number.isNaN(date.getTime())
          ? String(state.attributes.updated)
          : new Intl.DateTimeFormat(this._hass?.locale?.language || undefined, {
              hour: "2-digit",
              minute: "2-digit",
            }).format(date);
        footer.textContent = `${labels.updated}: ${value}`;
        wrapper.append(footer);
      }
    }

    card.append(wrapper);
    this.shadowRoot.replaceChildren(this._style(), card);
  }

  _message(text) {
    const message = document.createElement("div");
    message.className = "message";
    message.textContent = text;
    return message;
  }

  _table(items, labels) {
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const headings = [labels.time, labels.train, labels.direction];
    if (this._config.show_status) {
      headings.push(labels.status);
    }

    for (const heading of headings) {
      const cell = document.createElement("th");
      cell.textContent = heading;
      headerRow.append(cell);
    }
    head.append(headerRow);
    table.append(head);

    const body = document.createElement("tbody");
    for (const item of items) {
      const row = document.createElement("tr");
      if (item.serviceMessage) {
        row.title = String(item.serviceMessage);
      }

      row.append(this._timeCell(item));
      row.append(this._textCell(item.trainId || "—", "train"));
      row.append(
        this._textCell(
          item.actualDirection || item.direction || "—",
          item.destinationChanged ? "direction changed" : "direction"
        )
      );

      if (this._config.show_status) {
        const status = ["delayed", "cancelled", "on_time"].includes(item.status)
          ? item.status
          : "on_time";
        const cell = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = `status ${status}`;
        badge.textContent = labels[status];
        cell.append(badge);
        row.append(cell);
      }

      body.append(row);
    }
    table.append(body);
    return table;
  }

  _timeCell(item) {
    const cell = document.createElement("td");
    cell.className = "time";
    const actual = this._shortTime(item.actualTime);
    const planned = this._shortTime(item.plannedTime);
    const primary = document.createElement("span");
    primary.textContent = actual || planned || "—";
    cell.append(primary);

    if (actual && planned && actual !== planned) {
      const original = document.createElement("span");
      original.className = "planned";
      original.textContent = planned;
      cell.append(original);
    }
    return cell;
  }

  _textCell(value, className) {
    const cell = document.createElement("td");
    cell.className = className;
    cell.textContent = String(value);
    return cell;
  }

  _shortTime(value) {
    return typeof value === "string" ? value.slice(0, 5) : "";
  }

  _style() {
    const style = document.createElement("style");
    style.textContent = `
      :host {
        display: block;
      }
      ha-card {
        overflow: hidden;
      }
      .wrapper {
        padding: 0 16px 12px;
      }
      .card-header {
        padding: 16px 0 8px;
        font-size: var(--ha-card-header-font-size, 24px);
        font-weight: 500;
        line-height: 1.2;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        table-layout: auto;
      }
      th,
      td {
        padding: 7px 8px;
        border-bottom: 1px solid var(--divider-color);
        text-align: left;
        vertical-align: middle;
        font-size: 0.9rem;
      }
      th {
        color: var(--secondary-text-color);
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
      }
      th:first-child,
      td:first-child {
        padding-left: 0;
      }
      th:last-child,
      td:last-child {
        padding-right: 0;
      }
      tbody tr:last-child td {
        border-bottom: 0;
      }
      .time {
        width: 1%;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
        font-weight: 600;
      }
      .planned {
        margin-left: 6px;
        color: var(--secondary-text-color);
        font-size: 0.78rem;
        font-weight: 400;
        text-decoration: line-through;
      }
      .train {
        width: 1%;
        white-space: nowrap;
      }
      .direction {
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .direction.changed::after {
        content: " *";
        color: var(--warning-color, #ff9800);
      }
      .status {
        display: inline-block;
        padding: 3px 7px;
        border-radius: 999px;
        white-space: nowrap;
        font-size: 0.72rem;
        font-weight: 600;
      }
      .status.delayed {
        background: rgba(255, 152, 0, 0.2);
        background: color-mix(in srgb, var(--warning-color, #ff9800) 20%, transparent);
        color: var(--warning-color, #ff9800);
      }
      .status.cancelled {
        background: rgba(219, 68, 55, 0.2);
        background: color-mix(in srgb, var(--error-color, #db4437) 20%, transparent);
        color: var(--error-color, #db4437);
      }
      .status.on_time {
        background: rgba(67, 160, 71, 0.2);
        background: color-mix(in srgb, var(--success-color, #43a047) 20%, transparent);
        color: var(--success-color, #43a047);
      }
      .message {
        padding: 20px 0;
        color: var(--secondary-text-color);
        text-align: center;
      }
      .footer {
        padding-top: 8px;
        color: var(--secondary-text-color);
        font-size: 0.72rem;
        text-align: right;
      }
      @media (max-width: 520px) {
        th,
        td {
          padding: 6px 4px;
          font-size: 0.82rem;
        }
        .status {
          padding: 2px 5px;
        }
      }
    `;
    return style;
  }
}

if (!customElements.get("my-station-card")) {
  customElements.define("my-station-card", MyStationCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "my-station-card")) {
  window.customCards.push({
    type: "my-station-card",
    name: "My Station Card",
    description: "Compact Rejseplanen departures from the My Station integration.",
    preview: true,
  });
}
