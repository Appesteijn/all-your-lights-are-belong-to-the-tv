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
    CONF_SHIELD_ENTITY,
)

_LOGGER = logging.getLogger(__name__)


def _zones_to_lights(user_input: dict) -> dict:
    lights = {}
    for zone in ("left", "right", "ceiling"):
        for entity_id in user_input.get(f"zone_{zone}", []):
            lights[entity_id] = zone
    return lights


def _lights_to_zones(lights: dict) -> dict:
    zones: dict[str, list] = {"zone_left": [], "zone_right": [], "zone_ceiling": []}
    for entity_id, zone in lights.items():
        key = f"zone_{zone}"
        if key in zones:
            zones[key].append(entity_id)
    return zones


def _options_schema(suggested: dict) -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_SHIELD_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player", multiple=False)
        ),
        vol.Optional("zone_left"): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="light", multiple=True)
        ),
        vol.Optional("zone_right"): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="light", multiple=True)
        ),
        vol.Optional("zone_ceiling"): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="light", multiple=True)
        ),
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
    })


class AmbientTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_ADB_PORT

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._host = user_input["adb_host"]
            self._port = user_input.get("adb_port", DEFAULT_ADB_PORT)
            error = await self._check_connection(self._host, self._port)
            if error is None:
                return await self.async_step_options()
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("adb_host"): str,
                vol.Optional("adb_port", default=DEFAULT_ADB_PORT): int,
            }),
            errors=errors,
        )

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            lights = _zones_to_lights(user_input)
            settings = {k: v for k, v in user_input.items() if not k.startswith("zone_")}
            return self.async_create_entry(
                title="All Your Lights",
                data={"adb_host": self._host, "adb_port": self._port},
                options={"lights": lights, **settings},
            )

        return self.async_show_form(
            step_id="options",
            data_schema=_options_schema({}),
        )

    async def _check_connection(self, host: str, port: int) -> str | None:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5
            )
            writer.close()
            await writer.wait_closed()
        except (OSError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Shield niet bereikbaar op %s:%s: %s", host, port, err)
            return "cannot_connect"
        return None

    @staticmethod
    def async_get_options_flow(config_entry):
        return AmbientTVOptionsFlow()


class AmbientTVOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            lights = _zones_to_lights(user_input)
            settings = {k: v for k, v in user_input.items() if not k.startswith("zone_")}
            return self.async_create_entry(data={"lights": lights, **settings})

        current_opts = self.config_entry.options
        current_zones = _lights_to_zones(current_opts.get("lights", {}))
        suggested = {**current_opts, **current_zones}

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _options_schema(suggested), suggested
            ),
        )
