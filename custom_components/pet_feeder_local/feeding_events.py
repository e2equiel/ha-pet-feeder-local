"""Turn observed MCU scheduled-row records into durable, deduplicated HA events."""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import Meal, _reverse_weekdays
from .const import DOMAIN

EVENT_SCHEDULED_FEEDING = DOMAIN + "_scheduled_feeding"


class ScheduledFeedingEvents:
    """Persist the cursor before emitting; never replay startup history as a new meal."""

    def __init__(self, hass: HomeAssistant, entry_id: str, device_id: str, title: str) -> None:
        self.hass, self.entry_id, self.device_id, self.title = hass, entry_id, device_id, title
        self.store: Store[dict[str, Any]] = Store(hass, 1, DOMAIN + ".events." + entry_id)
        self.loaded = False
        self.cursor: dict[str, Any] | None = None

    async def async_process(self, result: dict[str, Any]) -> None:
        boot, sequence, events = result.get("boot_id"), result.get("sequence"), result.get("events")
        if (not isinstance(boot, str) or not re.fullmatch(r"[0-9a-f]{32}", boot)
            or type(sequence) is not int or not 0 <= sequence <= 0xffffffff
            or not isinstance(events, list) or len(events) > 16):
            raise ValueError("Invalid scheduled-event envelope")
        parsed: list[dict[str, Any]] = []
        previous = 0
        for item in events:
            if not isinstance(item, dict):
                raise ValueError("Invalid scheduled-event record")
            seq, age = item.get("sequence"), item.get("age_ms")
            if (type(seq) is not int or not previous < seq <= sequence
                or type(age) is not int or not 0 <= age <= 600000):
                raise ValueError("Invalid scheduled-event ordering or age")
            meal = Meal.from_json(item["meal"])
            if not meal.enabled:
                raise ValueError("Disabled row cannot be a scheduled execution")
            meal_data = asdict(meal)
            meal_data["weekdays"] = _reverse_weekdays(meal.weekdays)
            parsed.append({"sequence": seq, "age_ms": age, "meal": meal_data})
            previous = seq
        if not self.loaded:
            self.cursor = await self.store.async_load()
            self.loaded = True
        cursor = self.cursor
        # First installation establishes a baseline. Later restarts retain the
        # cursor and may recover fresh reports that occurred while HA was down.
        last = (cursor["sequence"] if cursor and cursor["boot_id"] == boot else 0) if cursor else sequence
        if sequence < last:
            raise ValueError("Scheduled-event sequence moved backwards")
        new_cursor = {"boot_id": boot, "sequence": sequence}
        if cursor != new_cursor:
            await self.store.async_save(new_cursor)
            self.cursor = new_cursor
        now = dt_util.utcnow()
        for item in parsed:
            if item["sequence"] <= last or item["age_ms"] > 120000:
                continue
            self.hass.bus.async_fire(EVENT_SCHEDULED_FEEDING, {
                "config_entry_id": self.entry_id, "device_id": self.device_id,
                "feeder_name": self.title, "event_id": f"{boot}-{item['sequence']}",
                "occurred_at": (now - timedelta(milliseconds=item["age_ms"])).isoformat(),
                "source": "mcu_scheduled_row", "meal": item["meal"],
                "physical_delivery_confirmed": False,
            })
