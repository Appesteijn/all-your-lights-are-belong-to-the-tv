import asyncio
import base64
import colorsys
import io
import logging
import struct
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    DEFAULT_CHANGE_THRESHOLD,
    DEFAULT_TRANSITION,
    DEFAULT_BRIGHTNESS_FACTOR,
    DEFAULT_SATURATION_BOOST,
    DEFAULT_UPDATE_INTERVAL_MS,
    ADB_KEY_PATH,
    ZONE_CEILING,
)

_LOGGER = logging.getLogger(__name__)

CAPTURE_W = 64
CAPTURE_H = 36

ZONE_BOUNDS = {
    "left":    (0.00, 0.30),
    "right":   (0.70, 1.00),
    "ceiling": (0.00, 1.00),
}


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
        self._device = None
        self._last_zone_colors: dict = {}
        self._key_path = Path(hass.config.config_dir) / ADB_KEY_PATH
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._task = self.hass.async_create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        _LOGGER.info("Ambient TV loop gestart — %d lamp(en) geconfigureerd: %s", len(self._lights), list(self._lights.keys()))
        while self._running:
            try:
                if self._device is None:
                    await self._connect()

                img = await self._capture()
                zones = self._analyze(img)

                updates = 0
                for entity_id, zone in self._lights.items():
                    if zone not in zones:
                        continue
                    zone_data = zones[zone]
                    last = self._last_zone_colors.get(zone)
                    if last and self._delta(last, zone_data) < self._threshold:
                        continue
                    self._last_zone_colors[zone] = zone_data
                    await self._update_light(entity_id, zone_data)
                    updates += 1

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

        # decode=False geeft raw bytes terug — geen base64 nodig
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

    async def _update_light(self, entity_id, zone_data):
        state = self.hass.states.get(entity_id)
        if state is None or state.state == "unavailable":
            return

        supported = state.attributes.get("supported_color_modes", [])

        if zone_data["type"] == "rgb" and any(m in supported for m in ("xy", "hs", "rgb")):
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
