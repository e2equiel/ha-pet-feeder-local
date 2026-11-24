"""Local feeder integration with MCU-owned feeding schedules."""
from __future__ import annotations

from pathlib import Path
from typing import cast

import probatio as vol
from aiohttp import ClientError
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FeederClient, FeederError, InvalidAuth, Meal
from .const import CONF_ADDRESS, CONF_TOKEN, DOMAIN
from .coordinator import FeederCoordinator

type FeederConfigEntry = ConfigEntry[FeederCoordinator]
PLATFORMS = [Platform.NUMBER, Platform.BUTTON, Platform.SENSOR,
             Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.CAMERA]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions and the bundled card once for the integration."""
    await hass.http.async_register_static_paths([StaticPathConfig(
        "/pet_feeder_local/frontend", str(Path(__file__).parent / "frontend"), True
    )])
    frontend.add_extra_js_url(hass, "/pet_feeder_local/frontend/pet-feeder-local-card.js?v=0.2.0")

    async def set_schedule(call: ServiceCall) -> None:
        target = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if target is None or target.domain != DOMAIN or target.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")
        try:
            meals = tuple(Meal(**meal) for meal in call.data["meals"])
        except (ValueError, TypeError) as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_schedule") from err
        coordinator = cast(FeederConfigEntry, target).runtime_data
        await coordinator.async_set_schedule(meals, call.data["expected_revision"])

    hass.services.async_register(DOMAIN, "set_schedule", set_schedule, schema=vol.Schema({
        vol.Required("config_entry_id"): str,
        vol.Required("expected_revision"): str,
        vol.Required("meals"): [dict],
    }))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FeederConfigEntry) -> bool:
    """Validate the device before creating entities."""
    client = FeederClient(async_get_clientsession(hass), entry.data[CONF_ADDRESS], entry.data[CONF_TOKEN])
    try:
        info = await client.async_get_info()
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="invalid_auth") from err
    except (FeederError, ClientError, TimeoutError, ValueError) as err:
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="cannot_connect") from err
    if entry.unique_id != info["id"]:
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="wrong_device")
    coordinator = FeederCoordinator(hass, entry, client, info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FeederConfigEntry) -> bool:
    """Unload entities and coordinator listeners without restarting HA."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
