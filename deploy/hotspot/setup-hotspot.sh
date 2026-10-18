#!/bin/bash
# One-time setup on the Pi: payload hotspot + captive portal + boot-time Wi-Fi mode choice.
#   sudo deploy/hotspot/setup-hotspot.sh "<ssid>" "<password>"
# The password is stored only in NetworkManager's config on the Pi - never commit it.
set -euo pipefail
SSID="$1"; PSK="$2"
CON=arachnid-hotspot
HERE=$(cd "$(dirname "$0")" && pwd)

apt-get install -y -q dnsmasq-base nftables >/dev/null

nmcli con delete "$CON" >/dev/null 2>&1 || true
# 2.4 GHz only: the ESP32 can't see 5 GHz. Started by payload-wifi, not by NetworkManager autoconnect.
nmcli con add type wifi ifname wlan0 con-name "$CON" autoconnect no ssid "$SSID" \
    802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
    ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
    wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp >/dev/null

mkdir -p /etc/NetworkManager/dnsmasq-shared.d
install -m 644 "$HERE/captive-dnsmasq.conf" /etc/NetworkManager/dnsmasq-shared.d/arachnid-captive.conf
install -m 644 "$HERE/captive.nft" /etc/arachnid-captive.nft
install -m 755 "$HERE/payload-wifi" /usr/local/bin/payload-wifi
install -m 644 "$HERE/payload-wifi.service" "$HERE/arachnid-captive.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable payload-wifi.service arachnid-captive.service
systemctl restart arachnid-captive.service
echo "Hotspot '$SSID' set up. It starts at boot when the home Wi-Fi isn't found; 'payload-wifi hotspot' starts it now."
