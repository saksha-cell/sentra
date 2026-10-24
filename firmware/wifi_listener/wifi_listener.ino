// WiFi listener (ESP32 #1) - captures probe requests and prints CSV over serial.
// Output line: MAC,RSSI,FINGERPRINT,TIMESTAMP_MS
#include <WiFi.h>
#include "esp_wifi.h"

#define RSSI_FLOOR -65     // ignore anything weaker than this
#define WIFI_CHANNEL 6     // channel the ESP32 listens on

// Turns a list of bytes into one short number (the fingerprint)
uint32_t fnv1aHash(uint8_t *data, int len) {
  uint32_t hash = 2166136261u;
  for (int i = 0; i < len; i++) {
    hash ^= data[i];
    hash *= 16777619u;
  }
  return hash;
}

void snifferCallback(void *buf, wifi_promiscuous_pkt_type_t type) {
  if (type != WIFI_PKT_MGMT) return;            // management frames only

  wifi_promiscuous_pkt_t *pkt = (wifi_promiscuous_pkt_t *)buf;
  uint8_t *payload = pkt->payload;
  int len = pkt->rx_ctrl.sig_len;

  if (payload[0] != 0x40) return;               // 0x40 = probe request

  int8_t rssi = pkt->rx_ctrl.rssi;
  if (rssi < RSSI_FLOOR) return;                // too far away, skip

  uint8_t *mac = payload + 10;                  // source MAC
  uint8_t *ie = payload + 24;                   // capability fields start here
  int ieLen = len - 24;
  int offset = 0;

  uint8_t structBuf[64];                        // tag + length pairs only
  int structLen = 0;

  while (offset + 2 <= ieLen && structLen < 62) {
    uint8_t tag = ie[offset];
    uint8_t tagLen = ie[offset + 1];
    if (offset + 2 + tagLen > ieLen) break;

    if (tag != 0) {                             // skip SSID (tag 0)
      structBuf[structLen++] = tag;
      structBuf[structLen++] = tagLen;
    }
    offset += 2 + tagLen;
  }

  uint32_t fingerprint = fnv1aHash(structBuf, structLen);
  unsigned long timestamp = millis();

  Serial.printf("%02X%02X%02X%02X%02X%02X,%d,%08X,%lu\n",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
                rssi, fingerprint, timestamp);
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_MODE_STA);
  WiFi.disconnect();
  delay(100);

  esp_wifi_set_promiscuous(true);
  esp_wifi_set_promiscuous_rx_cb(&snifferCallback);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
}

void loop() {
  delay(1000);
}
