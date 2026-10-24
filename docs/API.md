# Backend API (for the dashboard)

`GET http://<laptop-ip>:8000` returns JSON (`application/json`). Poll every 1-2 s. CORS is enabled. No auth.

```json
{
  "count": 4,
  "raw_count": 17,
  "phones_random_mac": 3,
  "real_mac_devices": 1,
  "threshold": 10,
  "alert": false
}
```

| Field | Type | Meaning |
|---|---|---|
| `count` | int | Fingerprint-based count of real devices (main number) |
| `raw_count` | int | Naive unique-MAC count, for comparison |
| `phones_random_mac` | int | Confirmed devices using randomized MACs (phones) |
| `real_mac_devices` | int | Confirmed devices with real MACs (laptops, routers, IoT) |
| `threshold` | int | Danger level |
| `alert` | bool | `true` when `count >= threshold` |

Only aggregate counts are returned: no MAC addresses, no fingerprints.
The backend keeps no history; the frontend stores its own readings for graphs.
