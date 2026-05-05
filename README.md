# All Your Lights Are Belong to the TV

A Home Assistant custom integration that creates a real-time Ambilight effect by capturing your NVIDIA Shield's screen via ADB and driving your Zigbee lights to match the screen colors.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## Requirements

- **NVIDIA Shield** (or other Android device with ADB over TCP)
- **Home Assistant** with ZHA or any light integration
- Lights with color support (RGB/XY/HS) for left/right/bottom zones
- Lights with color temperature support for ceiling zone (optional)

## Installation via HACS

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `Appesteijn/all-your-lights-are-belong-to-the-tv` as type **Integration**
3. Install "All Your Lights Are Belong to the TV"
4. Restart Home Assistant

## Setup

### 1. Enable ADB on the Shield

On your NVIDIA Shield:
**Settings → Device Preferences → Developer Options → Network debugging → On**

When prompted on the Shield screen, approve the connection from Home Assistant.

### 2. Add the integration

Go to **Settings → Integrations → Add integration** and search for "All Your Lights".

Enter the Shield's IP address (default port 5555).

### 3. Configure zones

Assign your lights to zones based on their position relative to the TV. Each zone analyzes a different region of the screen:

```
Screen region used per zone:

┌──────────────────────────────────────────────┐
│  LEFT   │                          │  RIGHT  │  ← full height
│  0–30%  │                          │ 70–100% │
│         ├──────── CEILING ─────────┤         │  ← top half (y 0–50%)
│         │                          │         │
│         ├──────── BOTTOM  ─────────┤         │  ← bottom half (y 50–100%)
└──────────────────────────────────────────────┘
```

| Zone | Screen region | Position | Mode |
|---|---|---|---|
| **Left** | Left 30%, full height | Left side / corner behind viewer | RGB |
| **Right** | Right 30%, full height | Right side / corner behind viewer | RGB |
| **Ceiling** | Full width, top 50% | Above the room | Color temperature |
| **Bottom** | Full width, bottom 50% | Below / in front of TV | RGB |

All zones are optional — leave a zone empty if you have no lights in that position.

Optionally select your Shield's **media player entity** to automatically start/stop the effect when the Shield turns on or off.

### 4. Switch entity

A `switch.ambilight` entity is created automatically. Use it to toggle the effect on/off from your dashboard or automations.

## Settings

| Setting | Default | Description |
|---|---|---|
| Transition | 0.7s | Light transition speed |
| Smoothing | 0.3 | Color change smoothness (0.1 = very calm, 1.0 = instant) |
| Brightness factor | 1.0 | Multiply screen brightness |
| Saturation boost | 1.4 | Make colors more vivid |
| Minimum color change | 12 | Ignore small changes (reduces flickering) |

## GLEDOPTO RGBW LED controllers (GL-C-007 etc.)

ZHA creates two entities per GLEDOPTO RGBW controller:
- **Entity 1** (`color_temp + xy`) → RGB color channel — **use this one in zones**
- **Entity 2** (`xy` only) → White channel — leave out of zones

The integration automatically turns off the white channel entity when sending color commands, preventing white LEDs from washing out the colors.

## Notes

- The integration only updates lights that are already **on** — it does not turn lights on by itself
- Screen capture runs continuously while active (~1–3 seconds per frame depending on Shield load)
- The ADB key pair is stored in `.adb/adbkey` inside your HA config directory
