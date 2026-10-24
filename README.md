# SENTRA - Crowd Density Early-Warning System

Estimates how crowded an area is by passively listening to WiFi probe requests from nearby phones. No cameras, no app installs.

**The hard part:** phones use random, rotating MAC addresses, so counting unique MACs badly overcounts (one phone looks like many). We identify the *same* phone across MAC changes using a fingerprint of its probe-request structure, RSSI, and timing.

## How it works

```
Phone -> ESP32 (promiscuous mode) -> USB serial -> Python backend -> JSON API -> Dashboard
```

1. **Firmware** (`firmware/wifi_listener`): ESP32 captures probe requests, skips the SSID, hashes the tag/length structure into a fingerprint, and prints `MAC,RSSI,FINGERPRINT,TIMESTAMP_MS`.
2. **Backend** (`backend/main.py`): two-stage matching.
   - Stage 1: a MAC seen before is the same device.
   - Stage 2: a new random MAC is matched to an existing device by fingerprint + similar RSSI + recent time.
3. **API**: live counts as JSON. See [docs/API.md](docs/API.md).

## Setup

**Firmware**
1. Install Arduino IDE and the ESP32 board package (Boards Manager -> "esp32" by Espressif).
2. Open `firmware/wifi_listener/wifi_listener.ino`, select **ESP32 Dev Module** and your port, upload.

**Backend**
```
pip install -r backend/requirements.txt
python backend/main.py
```
Edit `PORT` in `main.py` to your ESP32's port (for example `COM9`). Close Arduino Serial Monitor first, since only one program can use the port.

Open `http://localhost:8000` to see live JSON.

## Tuning (top of `backend/main.py`)

| Setting | Default | Controls |
|---|---|---|
| `RSSI_TOLERANCE` | 10 dBm | How different the signal can be for a rotated MAC to still match |
| `MATCH_WINDOW` | 60 s | How long after last seen a device can be re-matched |
| `EXPIRY_SECONDS` | 90 s | When a silent device is dropped |
| `MIN_PACKETS` | 2 | Packets needed before a device counts |
| `ALERT_THRESHOLD` | 10 | Count that triggers the alert |

On the ESP32, `RSSI_FLOOR` (in the `.ino`) sets the detection radius. Higher (for example -55) means a smaller zone.

## Known limitations

- Two phones of the same model and OS, standing close together, can share a fingerprint and be undercounted as one. This is a documented open problem.
- Phones with the screen off probe rarely, so the count is tuned for active-crowd scenarios.
- The fingerprint covers tag/length structure only, because newer phones randomize content bytes to defeat fingerprinting.
- WiFi must be on for a phone to be seen; the count is a proxy and needs per-site calibration.

## Privacy

The system reads only management frames, discards SSIDs, and exposes only aggregate counts. The optional `raw_log.csv` contains MACs; it is git-ignored and should be deleted after testing.

## Team

Team Golden Dawn
