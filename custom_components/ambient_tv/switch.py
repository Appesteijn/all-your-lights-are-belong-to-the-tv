from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AmbientTVCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AmbientTVCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AmbientTVSwitch(coordinator, entry)])


class AmbientTVSwitch(SwitchEntity):
    _attr_icon = "mdi:television-ambient-light"
    _attr_translation_key = "screen_sync"

    def __init__(self, coordinator: AmbientTVCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_name = "Screen sync"
        self._attr_unique_id = f"{entry.entry_id}_switch"

    @property
    def is_on(self) -> bool:
        return self._coordinator.enabled

    async def async_turn_on(self, **kwargs) -> None:
        self._coordinator.enable()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._coordinator.disable()
        self.async_write_ha_state()
