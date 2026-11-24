"""Expose the MCU table for the schedule editor."""
from homeassistant.components.sensor import SensorEntity
from .entity import FeederEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ScheduleSensor(entry.runtime_data, entry.entry_id)])


class ScheduleSensor(FeederEntity, SensorEntity):
    _attr_name = "Scheduled meals"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, "schedule")
        self._entry_id = entry_id

    @property
    def native_value(self):
        return len(self.coordinator.schedule.meals)

    @property
    def extra_state_attributes(self):
        return {"config_entry_id": self._entry_id,
                **self.coordinator.schedule_attributes()}
