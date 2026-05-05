# All Your Lights Are Belong to the TV

A Home Assistant custom integration that creates a real-time screen color sync effect by capturing your Android device's screen via ADB and driving your smart lights to match the colors on screen.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## Requirements

- **Android device** with ADB network debugging support (NVIDIA Shield, Android TV, Google TV, Fire TV Stick, etc.)
- **Home Assistant** with any light integration (ZHA, Z2M, Matter, etc.)
- Lights with **RGB/color support** for left, right, and bottom zones
- Lights with **color temperature support** for the ceiling zone (optional)

## Installation via HACS

> Don't have HACS yet? Install it first: [hacs.xyz](https://hacs.xyz/docs/use/download/download/)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `Appesteijn/all-your-lights-are-belong-to-the-tv` as type **Integration**
3. Install "All Your Lights Are Belong to the TV"
4. Restart Home Assistant

## Setup

### 1. Enable ADB network debugging on your Android device

The exact path varies by device and launcher, but typically:

**Settings → Device Preferences → Developer Options → Network debugging → On**

The first time Home Assistant connects, your device will show a prompt asking you to approve the ADB connection. **Accept it** — otherwise the integration cannot connect.

> If you don't see Developer Options: go to **About** and tap the build number 7 times to unlock it.

### 2. Add the integration

Go to **Settings → Integrations → Add integration** and search for **"All Your Lights"**.

Enter the device's IP address (default port 5555). You can find the IP in your router or under **Settings → Network → IP address** on the device.

### 3. Configure zones

Assign your lights to zones based on their position relative to the TV. Each zone analyzes a different region of the captured screen:

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

| Zone | Screen region | Typical light position | Mode |
|---|---|---|---|
| **Left** | Left 30%, full height | Left of TV | RGB |
| **Right** | Right 30%, full height | Right of TV | RGB |
| **Ceiling** | Full width, top 50% | Above / ceiling | Color temperature |
| **Bottom** | Full width, bottom 50% | Below / floor | RGB |

All zones are optional — leave a zone empty if you have no lights there.

### 4. Select a media player entity (optional)

If you select your device's **media player entity**, screen sync automatically starts when the device turns on and stops when it turns off or goes to standby.

### 5. Switch entity

A `switch.screen_sync` entity is created automatically. Use it to toggle the effect on/off from your dashboard or automations.

## Settings

| Setting | Default | Description |
|---|---|---|
| Capture interval | 500ms | How often the screen is captured. Lower = faster but more CPU load |
| Transition time | 0.7s | How long lights fade between colors |
| Smoothing | 0.3 | Blends frames together. 0.1 = very smooth, 1.0 = instant |
| Brightness multiplier | 1.0 | 1.0 = match screen brightness, 2.0 = double |
| Saturation multiplier | 1.4 | 1.0 = natural colors, higher = more vivid |
| Change sensitivity | 12 | Minimum color difference before updating lights. Higher = less flickering |
| Suppress sibling channels | On | See GLEDOPTO section below |

## GLEDOPTO RGBW LED controllers (GL-C-007 etc.)

ZHA registers two entities per GLEDOPTO RGBW controller:
- **Entity 1** (`color_temp + xy`) → RGB color channel — **use this one in zones**
- **Entity 2** (`xy` only) → White channel — leave out of zones

When **Suppress sibling channels** is enabled, the integration automatically turns off the white channel when sending color commands, preventing it from washing out the colors. Enable this setting if you have GLEDOPTO dual-channel hardware; leave it off otherwise.

## Notes

- The integration only updates lights that are already **on** — it does not turn lights on by itself
- When the media player goes to standby or off, screen sync pauses automatically (if configured)
- The ADB key pair is stored at `.adb/adbkey` inside your HA config directory and persists across restarts
