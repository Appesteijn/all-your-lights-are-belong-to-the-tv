import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import AmbientTVCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = AmbientTVCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Kan Shield niet bereiken via ADB ({entry.data.get('adb_host')}): {err}"
        ) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    _LOGGER.info("Ambient TV gestart met %d lamp(en)", len(entry.data.get("lights", {})))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: AmbientTVCoordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        coordinator.update_interval = None
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
