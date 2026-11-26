"""Poll local state, serialize writes, and report MCU connectivity repairs."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import timedelta
from time import monotonic
from typing import TYPE_CHECKING, Any, TypedDict

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    FeederClient,
    FeederError,
    FeederInfo,
    FeederStatus,
    FeedOutcomeUnknown,
    InvalidAuth,
    Meal,
    Schedule,
    ScheduleConflict,
    ScheduleVerificationError,
)
from .const import DOMAIN
from .feeding_events import ScheduledFeedingEvents

if TYPE_CHECKING:
    from . import FeederConfigEntry

_LOGGER = logging.getLogger(__name__)


class FeederData(TypedDict):
    status: FeederStatus
    schedule: Schedule


class FeederCoordinator(DataUpdateCoordinator[FeederData]):
    """Home Assistant synchronizes wall time but never executes meal schedules."""

    def __init__(self, hass: HomeAssistant, entry: FeederConfigEntry, client: FeederClient, info: FeederInfo) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(seconds=30))
        self.client = client
        self.info = info
        self.selected_portions = 1
        self.lock = asyncio.Lock()
        self.last_clock_sync = float("-inf")
        self._issue_id = entry.entry_id + "_mcu"
        self.feed_events = ScheduledFeedingEvents(hass, entry.entry_id, info["id"], entry.title)

    async def _async_update_data(self) -> FeederData:
        try:
            async with self.lock:
                status = await self.client.async_get_status()
                if status["mcu_connected"] and monotonic() - self.last_clock_sync >= 300:
                    await self.client.async_set_clock(dt_util.now())
                    self.last_clock_sync = monotonic()
                schedule = await self.client.async_get_schedule()
                if self.info.get("scheduled_feed_events") is True:
                    events = await self.client.async_get_events()
                    await self.feed_events.async_process(events)
            if status["mcu_connected"] and not status["serial_fault"]:
                ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
            else:
                ir.async_create_issue(self.hass, DOMAIN, self._issue_id, is_fixable=False,
                                      severity=ir.IssueSeverity.ERROR, translation_key="mcu_disconnected")
            return {"status": status, "schedule": schedule}
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="invalid_auth") from err
        except (FeederError, ClientError, TimeoutError, ValueError, KeyError) as err:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="cannot_connect") from err

    @property
    def schedule(self) -> Schedule:
        return self.data["schedule"]

    @property
    def mcu_ready(self) -> bool:
        return self.last_update_success and self.data["status"]["mcu_connected"] and not self.data["status"]["serial_fault"]

    def schedule_attributes(self) -> dict[str, Any]:
        return {"revision": self.schedule.revision, "integration": DOMAIN,
                "meals": [asdict(meal) for meal in self.schedule.meals]}

    async def async_serve(self) -> None:
        if not self.info["feeding_enabled"] or not self.mcu_ready:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="feeding_disabled")
        portions = self.selected_portions
        async with self.lock:
            try:
                await self.client.async_feed(portions)
            except FeedOutcomeUnknown as err:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="feed_unknown") from err
            except (FeederError, ClientError, TimeoutError, ValueError, KeyError) as err:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="action_failed") from err

    async def async_set_schedule(self, meals: tuple[Meal, ...], revision: str) -> None:
        async with self.lock:
            try:
                schedule = await self.client.async_set_schedule(meals, revision)
            except ScheduleConflict as err:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="schedule_conflict") from err
            except ScheduleVerificationError as err:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="schedule_verification") from err
            except (FeederError, ClientError, TimeoutError, ValueError, KeyError) as err:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="action_failed") from err
        self.async_set_updated_data({**self.data, "schedule": schedule})
