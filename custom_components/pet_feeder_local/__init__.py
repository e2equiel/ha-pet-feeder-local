"""Local feeder integration with MCU-owned feeding schedules."""
import probatio as vol
from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import FeederClient, InvalidAuth, Meal
from .const import CONF_ADDRESS, CONF_TOKEN, DOMAIN
from .coordinator import FeederCoordinator

PLATFORMS = [Platform.NUMBER, Platform.BUTTON, Platform.SENSOR,
             Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.CAMERA]


async def async_setup_entry(hass, entry) -> bool:
    client = FeederClient(async_get_clientsession(hass),
                          entry.data[CONF_ADDRESS], entry.data[CONF_TOKEN])
    try:
        info = await client.async_get_info()
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed from err
    except Exception as err:
        raise ConfigEntryNotReady("Cannot reach the feeder's local API") from err
    if info.get("api_version") != 1 or not info.get("id"):
        raise ConfigEntryNotReady("Unsupported feeder API response")
    coordinator = FeederCoordinator(hass, entry, client, info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def set_schedule(call):
        target = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if target is None or target.domain != DOMAIN or target.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError("Select a loaded Pet Feeder Local entry")
        try:
            meals = tuple(Meal(**meal) for meal in call.data["meals"])
        except (ValueError, TypeError) as err:
            raise HomeAssistantError("Invalid meal table") from err
        await target.runtime_data.async_set_schedule(meals, call.data["expected_revision"])

    if not hass.services.has_service(DOMAIN, "set_schedule"):
        hass.services.async_register(DOMAIN, "set_schedule", set_schedule, schema=vol.Schema({
            vol.Required("config_entry_id"): str,
            vol.Required("expected_revision"): str,
            vol.Required("meals"): [dict],
        }))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
