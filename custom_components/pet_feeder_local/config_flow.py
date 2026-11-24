"""Configure a feeder using its own local API token."""
from aiohttp import ClientError
from urllib.parse import urlsplit
import probatio as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
from .api import FeederClient, FeederError, InvalidAuth
from .const import CONF_ADDRESS, CONF_TOKEN, CONF_STREAM_SOURCE, DOMAIN


class PetFeederFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                client = FeederClient(async_get_clientsession(self.hass),
                                      user_input[CONF_ADDRESS], user_input[CONF_TOKEN])
                if source := user_input.get(CONF_STREAM_SOURCE):
                    parsed = urlsplit(source)
                    if parsed.scheme not in ("rtsp", "rtsps") or not parsed.hostname:
                        raise ValueError("Enter a local RTSP restream address")
                info = await client.async_get_info()
                if info.get("api_version") != 1 or not info.get("id"):
                    raise ValueError("Unsupported API")
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except (FeederError, ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_response"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Pet Feeder Local", data=user_input)
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_ADDRESS): str,
            vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional(CONF_STREAM_SOURCE, default=""): str,
        }))
