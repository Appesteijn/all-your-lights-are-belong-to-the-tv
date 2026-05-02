import asyncio
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_ADB_PORT,
    DEFAULT_UPDATE_INTERVAL_MS,
    DEFAULT_TRANSITION,
    DEFAULT_BRIGHTNESS_FACTOR,
    DEFAULT_SATURATION_BOOST,
    DEFAULT_CHANGE_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


class AmbientTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input["adb_host"]
            port = user_input.get("adb_port", DEFAULT_ADB_PORT)
            error = await self._check_connection(host, port)
            if error is None:
                self._data.update(user_input)
                return await self.async_step_lights()
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("adb_host"): str,
                vol.Optional("adb_port", default=DEFAULT_ADB_PORT): int,
            }),
            errors=errors,
        )

    async def async_step_lights(self, user_input=None):
        if user_input is not None:
            lights = {}
            for zone in ("left", "right", "ceiling"):
                for entity_id in user_input.get(f"zone_{zone}", []):
                    lights[entity_id] = zone
            self._data["lights"] = lights
            return await self.async_step_settings()

        return self.async_show_form(
            step_id="lights",
            data_schema=vol.Schema({
                vol.Optional("zone_left"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light", multiple=True)
                ),
                vol.Optional("zone_right"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light", multiple=True)
                ),
                vol.Optional("zone_ceiling"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light", multiple=True)
                ),
            }),
        )

    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="All Your Lights", data=self._data)

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Optional("update_interval_ms", default=DEFAULT_UPDATE_INTERVAL_MS): vol.All(
                    int, vol.Range(min=100, max=2000)
                ),
                vol.Optional("transition", default=DEFAULT_TRANSITION): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=2.0, step=0.1, unit_of_measurement="s")
                ),
                vol.Optional("brightness_factor", default=DEFAULT_BRIGHTNESS_FACTOR): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=2.0, step=0.1)
                ),
                vol.Optional("saturation_boost", default=DEFAULT_SATURATION_BOOST): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1.0, max=3.0, step=0.1)
                ),
                vol.Optional("change_threshold", default=DEFAULT_CHANGE_THRESHOLD): vol.All(
                    int, vol.Range(min=1, max=50)
                ),
            }),
        )

    async def _check_connection(self, host: str, port: int) -> str | None:
        """Geeft None terug bij succes, of een error-key bij fout."""
        # Stap 1: TCP bereikbaarheid
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5
            )
            writer.close()
            await writer.wait_closed()
        except (OSError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Shield niet bereikbaar op %s:%s: %s", host, port, err)
            return "cannot_connect"

        # Stap 2: ADB handshake — mislukt bij eerste keer (auth prompt op TV)
        # We slaan dit over: de coordinator verbindt bij opstarten en toont
        # de auth-prompt op de Shield. Gebruiker keurt eenmalig goed.
        _LOGGER.info("Shield bereikbaar op %s:%s, ADB auth volgt bij eerste start", host, port)
        return None
