"""Configure, rediscover, reconfigure and reauthenticate one local feeder."""
from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
from typing import Any
from urllib.parse import urlsplit

import probatio as vol
from aiohttp import ClientError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .api import FeederClient, FeederError, InvalidAuth
from .const import CONF_ADDRESS, CONF_STREAM_SOURCE, CONF_TOKEN, DOMAIN


class PetFeederFlow(ConfigFlow, domain=DOMAIN):
    """Local-only configuration; credentials are never sent to a cloud."""

    VERSION = 1
    _discovered_address = ""
    _discovered_id = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._configure("user", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._configure("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._configure("reconfigure", user_input)

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> ConfigFlowResult:
        """Update a known feeder address, or ask for its private token."""
        try:
            location = urlsplit(discovery_info.ssdp_location or "")
            address = IPv4Address(location.hostname or "")
            identity = discovery_info.upnp.get("serialNumber")
            if (location.scheme != "http" or location.port != 8080 or location.username or location.password
                or location.path != "/description.xml" or location.query or location.fragment
                or not isinstance(identity, str) or not 1 <= len(identity) <= 40
                or not any(address in IPv4Network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))):
                raise ValueError("Unsupported discovery")
        except ValueError:
            return self.async_abort(reason="invalid_discovery")
        self._discovered_address = f"http://{location.hostname}:8080"
        self._discovered_id = identity
        await self.async_set_unique_id(identity)
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: self._discovered_address})
        self.context["title_placeholders"] = {"name": "Pet Feeder Local"}
        return await self.async_step_user()

    async def _configure(self, step: str, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry() if step == "reauth_confirm" else self._get_reconfigure_entry() if step == "reconfigure" else None
        defaults = dict(entry.data) if entry else {CONF_ADDRESS: self._discovered_address}
        if user_input is not None:
            data = {**defaults, **user_input}
            try:
                client = FeederClient(async_get_clientsession(self.hass), data[CONF_ADDRESS], data[CONF_TOKEN])
                if source := data.get(CONF_STREAM_SOURCE):
                    parsed = urlsplit(source)
                    if parsed.scheme not in ("rtsp", "rtsps") or not parsed.hostname:
                        raise ValueError("Invalid restream URL")
                info = await client.async_get_info()
                expected = entry.unique_id if entry else self._discovered_id
                if expected and info["id"] != expected:
                    errors["base"] = "wrong_device"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except (FeederError, ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_response"
            if not errors:
                await self.async_set_unique_id(info["id"])
                if entry:
                    return self.async_update_reload_and_abort(entry, data_updates=data)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Pet Feeder Local", data=data)
        schema: dict[Any, Any] = {
            vol.Required(CONF_ADDRESS, default=defaults.get(CONF_ADDRESS, "")): str,
            vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional(CONF_STREAM_SOURCE, default=defaults.get(CONF_STREAM_SOURCE, "")): str,
        }
        return self.async_show_form(step_id=step, errors=errors, data_schema=vol.Schema(schema))
