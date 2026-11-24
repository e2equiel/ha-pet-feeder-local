"""A separate explicit Serve action."""
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FeederConfigEntry
from .coordinator import FeederCoordinator
from .entity import FeederEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: FeederConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([ServeButton(entry.runtime_data)])


class ServeButton(FeederEntity, ButtonEntity):

    def __init__(self, coordinator: FeederCoordinator) -> None:
        super().__init__(coordinator, "serve")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.info["feeding_enabled"] and self.coordinator.mcu_ready

    async def async_press(self) -> None:
        await self.coordinator.async_serve()
