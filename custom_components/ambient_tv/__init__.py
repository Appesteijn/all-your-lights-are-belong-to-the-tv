import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AmbientTVCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = AmbientTVCoordinator(hass, entry)

    # Dummy listener zodat de coordinator blijft pollen zonder entities
    remove_listener = coordinator.async_add_listener(lambda: None)
    entry.async_on_unload(remove_listener)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Start in achtergrond — blokkeert setup niet, Shield kan auth tonen
    hass.async_create_task(coordinator.async_refresh())

    lights = {**entry.data, **entry.options}.get("lights", {})
    _LOGGER.info("Ambient TV gestart met %d lamp(en)", len(lights))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: AmbientTVCoordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        coordinator.update_interval = None
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
