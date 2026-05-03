import asyncio
import colorsys
import logging
import struct
from pathlib import Path

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    DEFAULT_CHANGE_THRESHOLD,
    DEFAULT_TRANSITION,
    DEFAULT_BRIGHTNESS_FACTOR,
    DEFAULT_SATURATION_BOOST,
    DEFAULT_UPDATE_INTERVAL_MS,
    DEFAULT_SMOOTHING,
    ADB_KEY_PATH,
    ZONE_CEILING,
    CONF_SHIELD_ENTITY,
)

_LOGGER = logging.getLogger(__name__)

CAPTURE_W = 64
CAPTURE_H = 36

ZONE_BOUNDS = {
    "left":    (0.00, 0.30),
    "right":   (0.70, 1.00),
    "ceiling": (0.00, 1.00),
}

_SHIELD_OFF_STATES = {"off", "standby", "unavailable", "idle"}


class AmbientTVCoordinator:
    def __init__(self, hass: HomeAssistant, entry) -> None:
        data = {**entry.data, **entry.options}
        self.hass = hass
        self._host: str = data.get("adb_host", "")
        self._port: int = data.get("adb_port", 5555)
        self._lights: dict[str, str] = data.get("lights", {})
        self._transition: float = data.get("transition", DEFAULT_TRANSITION)
        self._brightness_factor: float = data.get("brightness_factor", DEFAULT_BRIGHTNESS_FACTOR)
        self._saturation_boost: float = data.get("saturation_boost", DEFAULT_SATURATION_BOOST)
        self._threshold: int = data.get("change_threshold", DEFAULT_CHANGE_THRESHOLD)
        self._smoothing: float = data.get("smoothing", DEFAULT_SMOOTHING)
        self._shield_entity: str | None = data.get(CONF_SHIELD_ENTITY)
        self._device = None
        self._last_zone_colors: dict = {}
        self._smoothed_zone_colors: dict = {}
        self._key_path = Path(hass.config.config_dir) / ADB_KEY_PATH
        self._task: asyncio.Task | None = None
        self._running = False
        self._enabled = True
        self._shield_active = True
        self._remove_shield_listener = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        _LOGGER.info("Ambilight ingeschakeld")

    def disable(self) -> None:
        self._enabled = False
        _LOGGER.info("Ambilight uitgeschakeld")

    @property
    def _should_run(self) -> bool:
        return self._enabled and self._shield_active

    def start(self) -> None:
        self._running = True
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._on_started)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._on_stop)

    def _on_started(self, _event) -> None:
        if self._shield_entity:
            self._remove_shield_listener = async_track_state_change_event(
                self.hass, [self._shield_entity], self._on_shield_state_change
            )
            state = self.hass.states.get(self._shield_entity)
            if state:
                self._shield_active = state.state not in _SHIELD_OFF_STATES
                _LOGGER.info("Shield staat op '%s' — ambilight %s", state.state, "actief" if self._shield_active else "inactief")

        self._task = self.hass.async_create_task(self._loop())

    def _smooth(self, current: dict, previous: dict | None) -> dict:
        if previous is None or self._smoothing >= 1.0:
            return current
        a = self._smoothing
        if current["type"] == "rgb":
            cr, cg, cb = current["rgb"]
            pr, pg, pb = previous["rgb"]
            return {**current, "rgb": (
                int(a * cr + (1 - a) * pr),
                int(a * cg + (1 - a) * pg),
                int(a * cb + (1 - a) * pb),
            )}
        cr, cg, cb = current["rgb"]
        pr, pg, pb = previous["rgb"]
        return {**current,
            "rgb": (int(a * cr + (1-a) * pr), int(a * cg + (1-a) * pg), int(a * cb + (1-a) * pb)),
            "ct_kelvin": int(a * current["ct_kelvin"] + (1-a) * previous["ct_kelvin"]),
            "brightness": int(a * current["brightness"] + (1-a) * previous["brightness"]),
        }

    def _on_shield_state_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        was_active = self._shield_active
        self._shield_active = new_state.state not in _SHIELD_OFF_STATES
        if self._shield_active != was_active:
            _LOGGER.info("Shield → '%s': ambilight %s", new_state.state, "gestart" if self._shield_active else "gestopt")
            if not self._shield_active:
                self._last_zone_colors.clear()
                self._smoothed_zone_colors.clear()

    def _on_stop(self, _event) -> None:
        self.stop()

    def stop(self) -> None:
        self._running = False
        if self._remove_shield_listener:
            self._remove_shield_listener()
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        _LOGGER.info("Ambient TV loop gestart — %d lamp(en) geconfigureerd: %s", len(self._lights), list(self._lights.keys()))
        while self._running:
            if not self._should_run:
                await asyncio.sleep(2)
                continue
            try:
                if self._device is None:
                    await self._connect()

                img = await self._capture()
                raw_zones = self._analyze(img)

                smoothed_zones = {
                    zone: self._smooth(data, self._smoothed_zone_colors.get(zone))
                    for zone, data in raw_zones.items()
                }
                self._smoothed_zone_colors = smoothed_zones

                changed = {
                    zone: data for zone, data in smoothed_zones.items()
                    if not self._last_zone_colors.get(zone)
                    or self._delta(self._last_zone_colors[zone], data) >= self._threshold
                }

                updates = 0
                for entity_id, zone in self._lights.items():
                    if zone not in changed:
                        continue
                    await self._update_light(entity_id, changed[zone])
                    updates += 1

                self._last_zone_colors.update(changed)

                if updates:
                    _LOGGER.debug("Frame verwerkt — %d lamp(en) bijgewerkt", updates)

            except asyncio.CancelledError:
                return
            except Exception:
                self._device = None
                _LOGGER.exception("Capture fout — loop paused 5s")
                await asyncio.sleep(5)

    async def _connect(self) -> None:
        from adb_shell.adb_device_async import AdbDeviceTcpAsync

        signer = await self.hass.async_add_executor_job(self._get_or_create_signer)
        self._device = AdbDeviceTcpAsync(self._host, self._port)
        await asyncio.wait_for(
            self._device.connect(rsa_keys=[signer], auth_timeout_s=30),
            timeout=35,
        )
        _LOGGER.info("Verbonden met Shield op %s:%d", self._host, self._port)

    def _get_or_create_signer(self):
        from adb_shell.auth.sign_pythonrsa import PythonRSASigner
        from adb_shell.auth.keygen import keygen

        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._key_path.exists():
            keygen(str(self._key_path))
        return PythonRSASigner.FromRSAKeyPath(str(self._key_path))

    async def _capture(self):
        from PIL import Image

        raw = await asyncio.wait_for(
            self._device.shell("screencap", decode=False),
            timeout=15,
        )
        # screencap raw formaat: 4B width, 4B height, 4B pixel_format, RGBA pixels
        w, h = struct.unpack_from("<II", raw, 0)
        img = Image.frombytes("RGBA", (w, h), raw[12:]).convert("RGB")
        return img.resize((CAPTURE_W, CAPTURE_H), Image.LANCZOS)

    def _analyze(self, img) -> dict:
        from PIL import ImageStat

        result = {}
        w, h = img.size

        for zone, (x_start_pct, x_end_pct) in ZONE_BOUNDS.items():
            x1 = int(w * x_start_pct)
            x2 = int(w * x_end_pct)
            region = img.crop((x1, 0, x2, h))
            stat = ImageStat.Stat(region)
            r, g, b = (int(v) for v in stat.mean[:3])

            if zone == ZONE_CEILING:
                result[zone] = {
                    "type": "ct",
                    "rgb": (r, g, b),
                    "ct_kelvin": self._rgb_to_ct(r, g, b),
                    "brightness": self._scene_brightness(r, g, b),
                }
            else:
                r2, g2, b2 = self._boost_color(r, g, b)
                result[zone] = {"type": "rgb", "rgb": (r2, g2, b2)}

        return result

    def _boost_color(self, r, g, b):
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        s = min(1.0, s * self._saturation_boost)
        v = min(1.0, v * self._brightness_factor)
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
        return (int(r2 * 255), int(g2 * 255), int(b2 * 255))

    def _scene_brightness(self, r, g, b):
        lum = int((0.299 * r + 0.587 * g + 0.114 * b) * self._brightness_factor)
        return max(10, min(255, lum))

    def _rgb_to_ct(self, r, g, b):
        warmth = r / max(b, 1)
        warmth = max(0.3, min(3.5, warmth))
        kelvin = int(2200 + (3.5 - warmth) / 3.2 * 4335)
        return max(2000, min(6535, kelvin))

    def _delta(self, a, b):
        if a.get("type") == "ct":
            return abs(a.get("ct_kelvin", 0) - b.get("ct_kelvin", 0)) // 10
        ra, ga, ba = a["rgb"]
        rb, gb, bb = b["rgb"]
        return max(abs(ra - rb), abs(ga - gb), abs(ba - bb))

    async def _turn_off_white_siblings(self, entity_id: str) -> None:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(self.hass)
        entry = registry.async_get(entity_id)
        if entry is None or entry.device_id is None:
            return

        for sibling in er.async_entries_for_device(registry, entry.device_id):
            if sibling.entity_id == entity_id or sibling.domain != "light":
                continue
            state = self.hass.states.get(sibling.entity_id)
            if state is None or state.state != "on":
                continue
            if state.attributes.get("color_mode") == "color_temp":
                _LOGGER.debug("Wit kanaal %s uitschakelen (zuster van %s)", sibling.entity_id, entity_id)
                await self.hass.services.async_call(
                    "light", "turn_off",
                    {"entity_id": sibling.entity_id, "transition": self._transition},
                    blocking=False,
                )

    async def _update_light(self, entity_id, zone_data):
        state = self.hass.states.get(entity_id)
        if state is None or state.state != "on":
            return

        supported = state.attributes.get("supported_color_modes", [])

        if zone_data["type"] == "rgb" and any(m in supported for m in ("xy", "hs", "rgb")):
            await self._turn_off_white_siblings(entity_id)
            r, g, b = zone_data["rgb"]
            await self.hass.services.async_call(
                "light", "turn_on",
                {"entity_id": entity_id, "rgb_color": [r, g, b], "transition": self._transition},
                blocking=False,
            )
        elif "color_temp" in supported:
            ct = zone_data.get("ct_kelvin") or self._rgb_to_ct(*zone_data["rgb"])
            brightness = zone_data.get("brightness") or self._scene_brightness(*zone_data["rgb"])
            await self.hass.services.async_call(
                "light", "turn_on",
                {"entity_id": entity_id, "color_temp_kelvin": ct, "brightness": brightness, "transition": self._transition},
                blocking=False,
            )
