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
    return {
      entity: entity || "",
      title: "Departures",
      icon: "mdi:train",
      icon_size: 32,
      max_rows: 8,
    };
  }

  setConfig(config) {
    if (!config || typeof config.entity !== "string" || !config.entity.trim()) {
      throw new Error("my-station-card requires a sensor entity");
    }

    const maxRows = Number(config.max_rows ?? 8);
    if (!Number.isInteger(maxRows) || maxRows < 1 || maxRows > 100) {
      throw new Error("max_rows must be an integer from 1 to 100");
    }

    const iconSize = Number(config.icon_size ?? 32);
    if (!Number.isInteger(iconSize) || iconSize < 1 || iconSize > 100) {
      throw new Error("icon_size must be an integer from 1 to 100");
    }

    const icon = config.icon === undefined ? "mdi:train" : String(config.icon).trim();

    this._config = {
      title: "Departures",
      show_status: true,
      show_updated: true,
      ...config,
      entity: config.entity.trim(),
      icon,
      icon_size: iconSize,
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

  getGridOptions() {
    return {
      columns: 12,
      rows: "auto",
      min_columns: 3,
      min_rows: 2,
    };
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

      if (this._config.icon) {
        const icon = document.createElement("ha-icon");
        icon.className = "title-icon";
        icon.setAttribute("icon", this._config.icon);
        icon.style.setProperty(
          "--my-station-title-icon-size",
          `${this._config.icon_size}px`
        );
        header.append(icon);
      }

      const title = document.createElement("span");
      title.className = "title-name";
      title.textContent = this._config.title;
      header.append(title);
      wrapper.append(header);
    }

    const content = document.createElement("div");
    content.className = "departure-content";
    wrapper.append(content);

    if (!state || state.state === "unavailable" || state.state === "unknown") {
      content.append(this._message(labels.unavailable));
    } else {
      const items = this._departureItems().slice(0, this._config.max_rows);
      if (items.length === 0) {
        content.append(this._message(labels.empty));
      } else {
        content.append(this._table(items, labels));
      }

      if (this._config.show_updated && state.attributes.updated) {
        wrapper.classList.add("has-footer");
        const footer = document.createElement("div");
        footer.className = "footer";
        const date = new Date(state.attributes.updated);
        const value = Number.isNaN(date.getTime())
          ? String(state.attributes.updated)
          : new Intl.DateTimeFormat(this._hass?.locale?.language || undefined, {
              hour: "2-digit",
              hourCycle: "h23",
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

    for (const [index, heading] of headings.entries()) {
      const cell = document.createElement("th");
      if (this._config.show_status && index === headings.length - 1) {
        cell.className = "status-column";
      }
      cell.textContent = heading;
      headerRow.append(cell);
    }
    head.append(headerRow);
    table.append(head);

    const body = document.createElement("tbody");
    for (const item of items) {
      const row = document.createElement("tr");
      const serviceMessage =
        typeof item.serviceMessage === "string" ? item.serviceMessage.trim() : "";
      if (serviceMessage) {
        row.className = "has-info";
        row.title = serviceMessage;
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
        cell.className = "status-column";
        const badge = document.createElement("span");
        badge.className = `status ${status}`;
        badge.textContent = labels[status];
        cell.append(badge);
        row.append(cell);
      }

      body.append(row);

      if (serviceMessage) {
        const infoRow = document.createElement("tr");
        infoRow.className = "departure-info-row";
        const infoCell = document.createElement("td");
        infoCell.colSpan = headings.length;
        infoCell.textContent = serviceMessage;
        infoRow.append(infoCell);
        body.append(infoRow);
      }
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
        width: 100%;
        height: 100%;
        min-height: 0;
      }
      ha-card {
        position: relative;
        overflow: hidden;
        width: 100%;
        height: 100%;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
      }
      .wrapper {
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
        height: 100%;
        width: 100%;
        min-height: 0;
        box-sizing: border-box;
        padding: 0 20px 12px 16px;
      }
      .wrapper.has-footer {
        padding-bottom: 48px;
      }
      .departure-content {
        flex: 0 1 auto;
        min-height: 0;
        overflow-y: auto;
      }
      .card-header {
        display: grid;
        grid-template-columns: auto 1fr;
        padding: 16px 0 8px;
        line-height: 1.2;
      }
      .title-name {
        place-self: center start;
        padding: 0 0 0 10px;
        font-size: 16px;
        font-weight: 500;
      }
      .title-icon {
        flex: 0 0 auto;
        width: var(--my-station-title-icon-size, 32px);
        height: var(--my-station-title-icon-size, 32px);
        color: orange;
        --mdc-icon-size: var(--my-station-title-icon-size, 32px);
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
        font-size: calc(0.9rem + 2px);
      }
      th {
        color: var(--accent-color);
        font-size: calc(0.75rem + 2px);
        font-weight: 600;
        text-transform: uppercase;
      }
      th:first-child,
      td:first-child {
        padding-left: 0;
      }
      th.status-column,
      td.status-column {
        padding-right: 0;
        width: 1%;
        white-space: nowrap;
        text-align: right;
      }
      tbody tr:last-child td {
        border-bottom: 0;
      }
      tbody tr.has-info td {
        padding-bottom: 2px;
        border-bottom: 0;
      }
      .departure-info-row td {
        padding-top: 0;
        color: #ff9800;
        font-size: calc(0.78rem + 2px);
        white-space: normal;
      }
      .time {
        width: 1%;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
        font-weight: 600;
      }
      .planned {
        margin-left: 6px;
        color: #ffeb3b;
        font-size: calc(0.78rem + 2px);
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
        border-radius: 3px;
        white-space: nowrap;
        font-size: calc(0.72rem + 2px);
        font-weight: 600;
      }
      .status.delayed {
        background: #ffeb3b;
        color: #000;
      }
      .status.cancelled {
        background: #d32f2f;
        color: #fff;
      }
      .status.on_time {
        background: #006400;
        color: #fff;
      }
      .message {
        padding: 20px 0;
        color: var(--secondary-text-color);
        font-size: calc(1rem + 2px);
        text-align: center;
      }
      .footer {
        position: absolute;
        right: 20px;
        bottom: 20px;
        color: var(--accent-color);
        font-size: calc(0.72rem + 2px);
        text-align: right;
      }
      @media (max-width: 520px) {
        th,
        td {
          padding: 6px 4px;
          font-size: calc(0.82rem + 2px);
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
