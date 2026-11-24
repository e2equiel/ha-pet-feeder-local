"""Allowlisted diagnostics: no credentials, addresses, identity or meal times."""
from homeassistant.core import HomeAssistant

from . import FeederConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: FeederConfigEntry) -> dict[str, object]:
    coordinator = entry.runtime_data
    return {"model": coordinator.info["model"], "overlay_version": coordinator.info["version"],
            "api_version": coordinator.info["api_version"],
            "last_update_success": coordinator.last_update_success,
            "mcu_connected": coordinator.data["status"]["mcu_connected"],
            "serial_fault": coordinator.data["status"]["serial_fault"],
            "clock_synced": coordinator.data["status"]["clock_synced"],
            "scheduled_rows": len(coordinator.schedule.meals),
            "enabled_rows": sum(meal.enabled for meal in coordinator.schedule.meals)}
