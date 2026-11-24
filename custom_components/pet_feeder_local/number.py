"""Portion selection is local UI state and never actuates the motor."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import FeederConfigEntry
from .const import DOMAIN
from .coordinator import FeederCoordinator
from .entity import FeederEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: FeederConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([PortionNumber(entry.runtime_data)])


class PortionNumber(FeederEntity, NumberEntity, RestoreEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1

    def __init__(self, coordinator: FeederCoordinator) -> None:
        super().__init__(coordinator, "portions")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            try:
                value = float(state.state)
                if value.is_integer() and 1 <= value <= 10:
                    self.coordinator.selected_portions = int(value)
            except ValueError:
                pass

    @property
    def native_value(self) -> int:
        return self.coordinator.selected_portions

    async def async_set_native_value(self, value: float) -> None:
        if not float(value).is_integer() or not 1 <= value <= 10:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_portions")
        self.coordinator.selected_portions = int(value)
        self.async_write_ha_state()
