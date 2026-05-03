# Ambient TV — CLAUDE.md

## Project

Home Assistant custom integration: real-time Ambilight effect via ADB screencap van NVIDIA Shield → Zigbee ledlampen.

- **Naam:** All Your Lights Are Belong to the TV
- **HA domain:** `ambient_tv`
- **HACS repo:** `Appesteijn/all-your-lights-are-belong-to-the-tv`

## Sourcecode

Alle broncode staat in `/home/mark/ha-ambient-tv/`.

```
custom_components/ambient_tv/
  __init__.py       — entry setup / unload
  coordinator.py    — ADB capture loop, zone analyse, lamp updates
  config_flow.py    — setup wizard + options flow
  switch.py         — switch.ambilight entiteit
  const.py          — defaults en constanten
  manifest.json     — versienummer (ophogen bij release)
  strings.json      — UI-teksten (Engels)
  translations/
    en.json
    nl.json
```

## Nieuwe release maken

1. Pas de code aan in `/home/mark/ha-ambient-tv/`
2. Verhoog het versienummer in `manifest.json`
3. Commit, tag en push:

```bash
cd /home/mark/ha-ambient-tv
git add -p
git commit -m "v1.x.y: omschrijving"
git tag v1.x.y
git push && git push --tags
```

4. Gebruiker updatet via HACS op de HA server en herstart HA.

## HA server

- URL: zie `/home/mark/hello-world/archive/.env` (`HA_URL` + `TOKEN`)
- HA draait op 192.168.1.130 (extern: hassio.dizzipline.com)
- Versie controleren: `GET /api/config`
- Lampstatus checken: `GET /api/states/<entity_id>`

## Hardware

- **Shield:** NVIDIA Shield TV op 192.168.1.168:5555 (ADB over TCP)
- **Ledstrips:** GLEDOPTO GL-C-007 RGBW controllers via ZHA
  - `light.led_links_light` → Links **Kleur** (RGB, gebruik in zone `left`)
  - `light.led_links_light_2` → Links **Wit** (white channel, niet in zones)
  - `light.led_rechts_light_3` → Rechts **Kleur** (RGB, gebruik in zone `right`)
  - `light.led_rechts_light_4` → Rechts **Wit** (white channel, niet in zones)
- **Plafondlampen:** zone `ceiling` (color temperature)

## Bekende quirks

- GLEDOPTO GL-C-007 heeft twee ZHA-entiteiten per controller: kleur (xy+color_temp) en wit (xy only). De wit-entiteit heeft een firmware-bug: xy:0,0 verschijnt als blauw. Beide kanalen kunnen tegelijk aan zijn (hardware regelt dit NIET zelf).
- Adaptive Lighting kan Wit-kanalen terugzetten; de coordinator draait `_turn_off_white_siblings` elke frame om dit tegen te gaan.
- `set_manual_control: True` wordt via de AL service gezet op Wit-siblings; wordt gereset bij HA herstart.
