"""Client and response helpers for the Rejseplanen API."""

from __future__ import annotations

import asyncio
import datetime as dt
import re
from typing import Any

import aiohttp

from .const import API_TIMEOUT_SECONDS, API_URL

PART_CANCELLED_NOTE_KEY = "text.realtime.journey.partially.cancelled.between"


class RejseplanenApiError(Exception):
    """Base exception for Rejseplanen API failures."""


class RejseplanenAuthenticationError(RejseplanenApiError):
    """Raised when Rejseplanen rejects the access ID."""


class RejseplanenConnectionError(RejseplanenApiError):
    """Raised when Rejseplanen cannot be reached or returns invalid data."""


class RejseplanenApiClient:
    """Small async client for Rejseplanen's departure board endpoint."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client with Home Assistant's shared session."""
        self._session = session

    async def async_get_departures(
        self,
        access_id: str,
        stop_id: str,
        max_journeys: int,
        duration: int,
    ) -> dict[str, Any]:
        """Fetch a departure board response."""
        params = {
            "accessId": access_id,
            "id": stop_id,
            "format": "json",
            "type": "DEP",
            "duration": str(duration),
            "lang": "da",
            "maxJourneys": str(max_journeys),
        }

        try:
            async with self._session.get(
                API_URL,
                params=params,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS),
            ) as response:
                if response.status in (401, 403):
                    raise RejseplanenAuthenticationError(
                        "Rejseplanen rejected the access ID"
                    )
                if response.status >= 400:
                    payload = await _async_read_error_json(response)
                    raise RejseplanenConnectionError(
                        _api_error_message(payload, f"HTTP {response.status}")
                    )
                payload = await _async_read_json(response)
        except RejseplanenApiError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise RejseplanenConnectionError(
                "Unable to connect to Rejseplanen"
            ) from err

        error_code = payload.get("errorCode")
        if error_code:
            message = _api_error_message(payload, str(error_code))
            if _looks_like_authentication_error(message):
                raise RejseplanenAuthenticationError(message)
            raise RejseplanenConnectionError(message)

        return payload


async def _async_read_error_json(
    response: aiohttp.ClientResponse,
) -> dict[str, Any]:
    """Best-effort decode an error response without masking its HTTP status."""
    try:
        payload = await response.json(content_type=None)
    except (aiohttp.ContentTypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


async def _async_read_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
    """Read an API response as a JSON object without trusting its content type."""
    try:
        payload = await response.json(content_type=None)
    except (aiohttp.ContentTypeError, ValueError) as err:
        raise RejseplanenConnectionError(
            "Rejseplanen returned an invalid JSON response"
        ) from err

    if not isinstance(payload, dict):
        raise RejseplanenConnectionError(
            "Rejseplanen returned an unexpected response"
        )
    return payload


def _api_error_message(payload: dict[str, Any], fallback: str) -> str:
    """Extract a useful, credential-safe API error message."""
    error_code = payload.get("errorCode")
    error_text = payload.get("errorText")
    if isinstance(error_text, str) and error_text.strip():
        if isinstance(error_code, str) and error_code.strip():
            return f"{error_code.strip()}: {error_text.strip()}"
        return error_text.strip()
    return fallback


def _looks_like_authentication_error(message: str) -> bool:
    """Return whether an API error describes rejected credentials."""
    normalized = message.casefold()
    return any(
        marker in normalized
        for marker in (
            "accessid",
            "access id",
            "authentication",
            "authorization",
            "forbidden",
            "unauthorized",
        )
    )


def parse_departure_datetime(
    date_value: object, time_value: object
) -> dt.datetime | None:
    """Parse the date/time format used by the departure board."""
    if not isinstance(date_value, str) or not isinstance(time_value, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(f"{date_value} {time_value}", fmt)
        except ValueError:
            continue
    return None


def listify(value: object) -> list[Any]:
    """Normalize a missing, scalar, or list API field to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def extract_note_text(note: dict[str, Any]) -> str | None:
    """Extract text from the variants returned for a Rejseplanen note."""
    for key in ("txtN", "value", "text"):
        value = note.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_partial_cancellation(note_text: str) -> tuple[str, str] | None:
    """Extract endpoints from a Danish partial-cancellation message."""
    match = re.search(
        r"mellem\s+(.+?)\s+og\s+(.+?)(?:\.+\s|$)",
        note_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def extract_destination_update(departure: dict[str, Any]) -> dict[str, Any]:
    """Apply the standalone app's partial-cancellation destination logic."""
    scheduled_direction = departure.get("direction")
    actual_direction = scheduled_direction
    destination_changed = False
    cancelled_between_from = None
    cancelled_between_to = None
    service_message = None

    notes = departure.get("Notes")
    if not isinstance(notes, dict):
        notes = {}

    for note in listify(notes.get("Note")):
        if not isinstance(note, dict):
            continue
        note_key = note.get("key")
        note_type = note.get("type")
        note_text = extract_note_text(note)

        if not service_message and note_text and note_type == "R":
            service_message = note_text

        if note_key != PART_CANCELLED_NOTE_KEY or not note_text:
            continue
        parsed = parse_partial_cancellation(note_text)
        if not parsed:
            continue
        cancelled_between_from, cancelled_between_to = parsed
        destination_changed = True
        actual_direction = cancelled_between_from

    return {
        "scheduledDirection": scheduled_direction,
        "actualDirection": actual_direction,
        "destinationChanged": destination_changed,
        "cancelledBetweenFrom": cancelled_between_from,
        "cancelledBetweenTo": cancelled_between_to,
        "serviceMessage": service_message,
    }


def compact_departure_data(
    payload: dict[str, Any], cat_out_filter: str | None = None
) -> list[dict[str, Any]]:
    """Create the compact departure rows used by the original app and card."""
    departures = listify(payload.get("Departure"))
    rows: list[dict[str, Any]] = []

    for departure in departures:
        if not isinstance(departure, dict):
            continue

        product_at_stop = departure.get("ProductAtStop")
        cat_out = (
            product_at_stop.get("catOut")
            if isinstance(product_at_stop, dict)
            else None
        )
        if (
            cat_out_filter
            and isinstance(cat_out, str)
            and cat_out.casefold() != cat_out_filter.casefold()
        ):
            continue

        planned_date = departure.get("date")
        planned_time = departure.get("time")
        actual_date = departure.get("rtDate")
        actual_time = departure.get("rtTime")
        cancelled = bool(departure.get("cancelled", False))

        status = "on_time"
        if cancelled:
            status = "cancelled"
        else:
            planned = parse_departure_datetime(planned_date, planned_time)
            actual = parse_departure_datetime(actual_date, actual_time)
            if planned and actual and actual > planned:
                status = "delayed"

        destination = extract_destination_update(departure)
        rows.append(
            {
                "trainId": departure.get("name"),
                "direction": departure.get("direction"),
                "scheduledDirection": destination["scheduledDirection"],
                "actualDirection": destination["actualDirection"],
                "destinationChanged": destination["destinationChanged"],
                "cancelledBetweenFrom": destination["cancelledBetweenFrom"],
                "cancelledBetweenTo": destination["cancelledBetweenTo"],
                "partCancelled": bool(departure.get("partCancelled", False)),
                "serviceMessage": destination["serviceMessage"],
                "departs": departure.get("stop"),
                "plannedDate": planned_date,
                "plannedTime": planned_time,
                "actualDate": actual_date,
                "actualTime": actual_time,
                "status": status,
            }
        )

    return rows


def build_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the compact envelope published by the standalone app."""
    return {
        "count": len(items),
        "items": items,
        "updated": dt.datetime.now(dt.timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds"),
        "ok": True,
        "error": None,
    }
