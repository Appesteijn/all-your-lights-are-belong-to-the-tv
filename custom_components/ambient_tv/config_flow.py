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


class AmbientTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._test_adb(user_input["adb_host"], user_input.get("adb_port", DEFAULT_ADB_PORT))
                self._data.update(user_input)
                return await self.async_step_lights()
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("adb_host"): str,
                vol.Optional("adb_port", default=DEFAULT_ADB_PORT): int,
            }),
            errors=errors,
            description_placeholders={
                "adb_info": "Schakel op de Shield in via: Instellingen → Apparaatvoorkeuren → Ontwikkelaarsopties → Netwerk-debuggen"
            },
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
            return self.async_create_entry(title="Ambient TV", data=self._data)

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

    async def _test_adb(self, host: str, port: int) -> None:
        from adb_shell.adb_device_async import AdbDeviceTcpAsync

        device = AdbDeviceTcpAsync(host, port, default_timeout_s=10)
        await device.connect(rsa_keys=[], auth_timeout_s=10)
        await device.close()
