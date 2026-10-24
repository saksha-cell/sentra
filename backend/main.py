"""Brain: reads ESP32 serial lines, counts real devices, serves JSON for the dashboard."""
import serial, time, threading, queue, json
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------- Settings (tune these) ----------
PORT = "COM9"
BAUD = 115200               # must match the ESP32 code
RSSI_TOLERANCE = 10         # dBm, for cross-burst matching
MATCH_WINDOW = 60           # sec, how long a device can be "re-matched"
EXPIRY_SECONDS = 90         # sec, device removed if not seen this long
MIN_PACKETS = 2             # packets needed before a device counts
ALERT_THRESHOLD = 10        # count at which alert turns on
HTTP_PORT = 8000
LOG_FILE = "raw_log.csv"    # every raw line saved here for offline replay

# ---------- Shared state (always use the lock) ----------
lock = threading.Lock()
line_queue = queue.Queue()
devices = {}        # dev_id -> {fps, rssi, last_seen, hits, random}
mac_to_dev = {}     # mac -> dev_id
raw_macs = {}       # mac -> last_seen (the "dumb" count, for comparison)
next_id = 0


def is_random(mac):
    # Second hex digit of first byte: 2, 6, A, E = randomized MAC
    return mac[1].upper() in "26AE"


# ---------- Thread 1: read serial, nothing else ----------
def reader():
    ser = serial.Serial(PORT, BAUD)
    with open(LOG_FILE, "a") as log:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            parts = line.split(",")
            if len(parts) == 4:
                line_queue.put((time.time(), parts))
                log.write(line + "\n")
                log.flush()


# ---------- The two-stage matching ----------
def process(now, mac, rssi, fp):
    global next_id
    raw_macs[mac] = now

    # STAGE 1: MAC already known -> same device (same burst)
    dev_id = mac_to_dev.get(mac)
    if dev_id in devices:
        d = devices[dev_id]
        d["rssi"] = rssi
        d["last_seen"] = now
        d["hits"] += 1
        d["fps"].add(fp)
        return

    # STAGE 2: new MAC -> try fingerprint + RSSI + time (MAC rotation case)
    matched = None
    if is_random(mac):   # real MACs never rotate, so no fingerprint matching
        for i, d in devices.items():
            if (d["random"]
                    and fp in d["fps"]
                    and abs(d["rssi"] - rssi) <= RSSI_TOLERANCE
                    and now - d["last_seen"] <= MATCH_WINDOW):
                matched = i
                break

    if matched is None:   # genuinely new device
        matched = next_id
        next_id += 1
        devices[matched] = {"fps": {fp}, "rssi": rssi, "last_seen": now,
                            "hits": 1, "random": is_random(mac)}
    else:                 # same phone, new MAC
        d = devices[matched]
        d["rssi"] = rssi
        d["last_seen"] = now
        d["hits"] += 1

    mac_to_dev[mac] = matched


# ---------- Thread 2: process queued lines ----------
def processor():
    while True:
        now, parts = line_queue.get()
        mac, rssi, fp, _ = parts
        try:
            rssi = int(rssi)
        except ValueError:
            continue
        with lock:
            process(now, mac, rssi, fp)


# ---------- Thread 3: expire old devices ----------
def expiry():
    while True:
        time.sleep(5)
        now = time.time()
        with lock:
            for i in [i for i, d in devices.items()
                      if now - d["last_seen"] > EXPIRY_SECONDS]:
                del devices[i]
            for m in [m for m, i in mac_to_dev.items() if i not in devices]:
                del mac_to_dev[m]
            for m in [m for m, t in raw_macs.items()
                      if now - t > EXPIRY_SECONDS]:
                del raw_macs[m]


# ---------- Current numbers ----------
def snapshot():
    with lock:
        confirmed = [d for d in devices.values() if d["hits"] >= MIN_PACKETS]
        return {
            "count": len(confirmed),
            "raw_count": len(raw_macs),
            "phones_random_mac": sum(d["random"] for d in confirmed),
            "real_mac_devices": sum(not d["random"] for d in confirmed),
            "threshold": ALERT_THRESHOLD,
            "alert": len(confirmed) >= ALERT_THRESHOLD,
        }


# ---------- Thread 4: print to console ----------
def printer():
    last = None
    while True:
        time.sleep(2)
        s = snapshot()
        if s != last:
            print(f"RAW MACs: {s['raw_count']} | OURS: {s['count']} "
                  f"(random: {s['phones_random_mac']}, real: {s['real_mac_devices']})"
                  f"{'  *** ALERT ***' if s['alert'] else ''}")
            last = s


# ---------- Web endpoint for the dashboard ----------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(snapshot()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    for fn in (reader, processor, expiry, printer):
        threading.Thread(target=fn, daemon=True).start()
    print(f"Running. Live data at http://localhost:{HTTP_PORT}")
    HTTPServer(("", HTTP_PORT), Handler).serve_forever()
