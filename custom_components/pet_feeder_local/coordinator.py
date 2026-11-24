"""Coordinate local reads and serialize writes to one feeder."""
import asyncio
from dataclasses import asdict
from datetime import timedelta
import logging
from time import monotonic

from aiohttp import ClientError
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import FeederClient, FeederError, InvalidAuth, Meal, Schedule
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FeederCoordinator(DataUpdateCoordinator):
    """Poll the MCU; Home Assistant never runs the feeding schedule."""

    def __init__(self, hass, entry, client: FeederClient, info: dict) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(seconds=30))
        self.client = client
        self.info = info
        self.selected_portions = 1
        self.lock = asyncio.Lock()
        self.last_clock_sync = float("-inf")

    async def _async_update_data(self) -> dict:
        try:
            async with self.lock:
                if monotonic() - self.last_clock_sync >= 300:
                    await self.client.async_set_clock(dt_util.now())
                    self.last_clock_sync = monotonic()
                status = await self.client.async_get_status()
                schedule = await self.client.async_get_schedule()
            return {"status": status, "schedule": schedule}
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("The feeder token was rejected") from err
        except (FeederError, ClientError, TimeoutError, ValueError, KeyError) as err:
            raise UpdateFailed("Cannot read the local feeder") from err

    @property
    def schedule(self) -> Schedule:
        return self.data["schedule"]

    def schedule_attributes(self) -> dict:
        return {"revision": self.schedule.revision,
                "meals": [asdict(meal) for meal in self.schedule.meals]}

    async def async_serve(self) -> None:
        if not self.info.get("feeding_enabled"):
            raise HomeAssistantError("Manual feeding is disabled on the device")
        # Capture the selection before awaiting. There is exactly one POST.
        portions = self.selected_portions
        async with self.lock:
            try:
                await self.client.async_feed(portions)
            except (FeederError, ClientError, TimeoutError, ValueError, KeyError) as err:
                raise HomeAssistantError(str(err)) from err

    async def async_set_schedule(self, meals: tuple[Meal, ...], revision: str) -> None:
        async with self.lock:
            try:
                schedule = await self.client.async_set_schedule(meals, revision)
            except (FeederError, ClientError, TimeoutError, ValueError, KeyError) as err:
                raise HomeAssistantError(str(err)) from err
        self.async_set_updated_data({**self.data, "schedule": schedule})
