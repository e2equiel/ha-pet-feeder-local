"""Expose the MCU table for the schedule editor."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FeederConfigEntry
from .coordinator import FeederCoordinator
from .entity import FeederEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: FeederConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([ScheduleSensor(entry.runtime_data, entry.entry_id)])


class ScheduleSensor(FeederEntity, SensorEntity):

    def __init__(self, coordinator: FeederCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, "schedule")
        self._entry_id = entry_id

    @property
    def native_value(self) -> int:
        return len(self.coordinator.schedule.meals)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        registry = er.async_get(self.hass)
        links = {field: registry.async_get_entity_id(platform, "pet_feeder_local", f"{self.coordinator.info['id']}_{key}")
                 for field, platform, key in (("portions_entity", "number", "portions"), ("serve_entity", "button", "serve"),
                                              ("camera_entity", "camera", "camera"), ("calendar_entity", "calendar", "calendar"))}
        return {"config_entry_id": self._entry_id, **links, **self.coordinator.schedule_attributes()}
