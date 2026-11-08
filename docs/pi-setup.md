# Raspberry Pi 5 setup

Fresh Pi 5 -> payload running. First done 2026-10-16; redone on a new card 2026-11-08 (the first card died).

| | |
|---|---|
| Hostname / IP | `arachnid` / 192.168.0.162 (DHCP - reserve it in the router) |
| User | `virologyst`. Passwordless sudo only works during the first boot on a fresh image - add `/etc/sudoers.d/010_virologyst-nopasswd` (user, via `sudo visudo -f`) so Claude can run sudo over SSH afterwards |
| OS | Raspberry Pi OS 64-bit, **Debian 13 Trixie**, kernel 6.18, Python 3.13 |
| Hardware | Pi 5 8 GB, 464 GB SD card (since 2026-11-08) |
| Repo | `~/Arachnid-Payload-System`, venv in `.venv` |

## 1. On the Windows PC: SSH key (once)

```powershell
ssh-keygen -t ed25519
```

Default location, empty passphrase (so Claude can connect unattended). Public key:
`C:\Users\<you>\.ssh\id_ed25519.pub`.

## 2. Flash the SD card (Raspberry Pi Imager 2.x)

- Device Raspberry Pi 5, OS **Raspberry Pi OS (64-bit)** (Trixie). Never 32-bit (no DepthAI wheels).
  Trixie works: depthai 3.11 installs on Python 3.13.
- Customisation: hostname `arachnid`, user, Wi-Fi (same network as huntsman.local, country AU), SSH with
  your public key.
- Imager settings don't reliably carry over: in 2026-10 only the hostname did; in 2026-11 Wi-Fi and the
  user did but not the hostname (`sudo hostnamectl set-hostname arachnid` + fix `/etc/hosts`) or SSH. Check after
  the first boot. A reflashed Pi has new host keys: on the PC, `ssh-keygen -R 192.168.0.162` clears the
  "REMOTE HOST IDENTIFICATION HAS CHANGED" error.

## 3. SSH access (if the key didn't carry over)

**Gotcha:** Trixie images use cloud-init, which writes `/etc/ssh/sshd_config.d/50-cloud-init.conf` with
`PasswordAuthentication no`, and the stock `sshd_config` has `PubkeyAuthentication no`. sshd uses the
**first** value it reads, and `sshd_config.d/*.conf` is read first, in name order - so a `00-*.conf` file
decides. Check the result with `sudo sshd -T | grep -i authentication`.

On the Pi (keyboard/screen), turn SSH on with passwords allowed for now:

```bash
printf "PubkeyAuthentication yes\nPasswordAuthentication yes\n" | sudo tee /etc/ssh/sshd_config.d/00-auth.conf
sudo systemctl enable --now ssh
```

Then copy the PC's key from PowerShell **or** cmd (full path - `$env:` / `%...%` only work in one of them;
`tr` strips Windows line endings, which sshd rejects):

```bash
type C:\Users\craig\.ssh\id_ed25519.pub | ssh virologyst@192.168.0.162 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d '\r' > ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Then make SSH keys-only:

```bash
printf "PubkeyAuthentication yes\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n" | sudo tee /etc/ssh/sshd_config.d/00-auth.conf
sudo systemctl reload ssh
```

## 4. System

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-dev i2c-tools nodejs npm   # Trixie's nodejs is 20.19 - enough for Vite 7
sudo raspi-config nonint do_i2c 0      # Enviro+ sensors
sudo raspi-config nonint do_boot_behaviour B4   # desktop, auto-login (a fresh image asks for the password)
```

SPI for the Enviro+ LCD: **not** `do_spi` / `dtparam=spi=on` - see the LCD note below.

Power check, any time: `vcgencmd get_throttled` should print `throttled=0x0`. Anything else means
undervoltage or overheating.

**On battery (buck converter) power, `usb_max_current_enable=1` in `/boot/firmware/config.txt` is required**
(set on this Pi 2026-10-16). A buck can't negotiate USB-PD, so the Pi assumes 3 A and limits USB to 600 mA
total - the OAK then resets every few seconds (`X_LINK_ERROR` in the log, video stalls). Only set it if the
supply really gives 5 A. Check: `vcgencmd pmic_read_adc EXT5V_V` (4.91-4.99 V seen on the 100 W USB-C charger module, which is fixed -
watch `get_throttled` under load instead).

**Enviro+ LCD on the Pi 5:** the LCD's DC pin is GPIO9, which `dtparam=spi=on` claims as SPI0 MISO, so
`st7735` can't take it and the LCD stays blank (`LCD init failed` in the log) while the I2C sensors work.
In `/boot/firmware/config.txt` use `dtoverlay=spi0-2cs,no_miso` instead of `dtparam=spi=on` (keeps
CS0/CS1, frees GPIO9), then reboot. Applied 2026-11-08: the log says `Enviro+ and LCD initialised correctly`.

**Spare the SD card** (the first card died 2026-11-08). The app itself writes nothing in normal running;
these stop the OS writing constantly too:

```bash
# System journal in RAM only (lost on reboot; capped at 50 MB)
sudo mkdir -p /etc/systemd/journald.conf.d
printf "[Journal]\nStorage=volatile\nRuntimeMaxUse=50M\n" | sudo tee /etc/systemd/journald.conf.d/volatile.conf
sudo rm -rf /var/log/journal && sudo systemctl restart systemd-journald
# Swap in RAM only: Trixie uses zram, plus a 2 GB /var/swap writeback file on the card - turn that off
sudo mkdir -p /etc/rpi/swap.conf.d
printf "[Main]\nMechanism=zram\n" | sudo tee /etc/rpi/swap.conf.d/90-no-disk-swap.conf   # applies on reboot
```

Check `/` is mounted `noatime` (`findmnt /` - Raspberry Pi OS sets it by default). Shut down before
cutting battery power where possible (`sudo shutdown now`, or the dashboard) - a power cut mid-write is
what corrupts cards.

Enviro+ check: `i2cdetect -y 1` should show 0x23 (LTR559), 0x49 (ADS1015 gas) and 0x76 (BME280).

## 4b. Hotspot (field use) and captive portal

One Wi-Fi radio: the Pi is **either** on the home network **or** runs the hotspot. At boot
`payload-wifi.service` waits up to 30 s for the home Wi-Fi and otherwise starts the hotspot.

| | |
|---|---|
| SSID | `Huntsman PL01` (2.4 GHz, channel 6, WPA2) - password: ask the user / NetworkManager on the Pi, never in git |
| Pi address on the hotspot | `10.42.0.1` - dashboard http://10.42.0.1 (port 80 is forwarded to 8080) |
| Robot | joins it as its second network (`WIFI_SSID_2` in Huntsman's git-ignored `secrets.h`); `huntsman.local` resolves over mDNS |

One-time setup (from the repo on the Pi):

```bash
sudo bash deploy/hotspot/setup-hotspot.sh "Huntsman PL01" "<password>"
```

Switch by hand: `payload-wifi hotspot` / `payload-wifi home` / `payload-wifi status` (switching drops SSH
over the network you leave - join the other network to reconnect).

**Captive portal:** on the hotspot every DNS name resolves to the Pi (`address=/#/10.42.0.1` in
NetworkManager's shared dnsmasq) and Flask redirects any foreign hostname to the dashboard, so a phone or
laptop that joins pops up "Sign in to network" showing the dashboard. The pop-up is a limited browser - use
its "open in browser" option for full use. Phones may report "no internet" and offer to switch back to
mobile data: choose to stay connected.

The robot only moves to the hotspot when it can't find the home network (it tries home first, then rotates).
If the Pi is forced into hotspot mode at home, the robot stays on the home network and the dashboard can't
reach it - restart the robot away from home Wi-Fi, or switch the Pi back with `payload-wifi home`.

## 5. OAK-D Lite

Plug into a **blue USB 3** port with a USB 3 cable. Access for normal users:

```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Check: `lsusb | grep 03e7`, then
`python -c "import depthai as dai; print(dai.Device.getAllAvailableDevices())"` in the venv.

## 6. Repo and Python

```bash
git clone https://github.com/Virologyst/Arachnid-Payload-System.git ~/Arachnid-Payload-System
cd ~/Arachnid-Payload-System
python3 -m venv --system-site-packages .venv     # keeps the Pi's own gpiozero / lgpio / picamera2
source .venv/bin/activate
pip install depthai "depthai-nodes==0.3.7" flask enviroplus pimoroni-bme280 ltr559 st7735 fonts font-roboto
```

**depthai-nodes must stay at 0.3.7**: `target_detection/inference.py` uses `ImgDetectionsBridge` (removed in
0.5) and its `setLabelEncoding()` (removed in 0.4). depthai-nodes brings `opencv-python-headless` (4.10, includes `cv2.aruco`) - don't add
another OpenCV package. Don't `pip install -r requirements.txt` - it is a whole-system `pip freeze` and
won't install cleanly. Installed as of 2026-11-08: depthai 3.12.0, depthai-nodes 0.3.7.

## 7. Dashboard (web UI)

```bash
cd ~/Arachnid-Payload-System/interface && npm install && npm run build
cd .. && rm -rf static && cp -r interface/build static
```

## 8. Run

Runs as a systemd service, started on boot (unit file in the repo: `deploy/payload.service`):

```bash
sudo install -m 644 ~/Arachnid-Payload-System/deploy/payload.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now payload
```

Day to day: `sudo systemctl restart payload` (after a `git pull`), `systemctl status payload`,
`journalctl -u payload -f` (live log). Settings below go in the unit as `Environment=` lines.
To run it by hand instead, stop the service first, then
`cd ~/Arachnid-Payload-System && .venv/bin/python app.py`.

The app starts without the OAK (dummy detections - a colour-cycling test image) or the Enviro+
(`/enviro` returns 503). The startup log says which hardware it found.

| Environment variable | Default | Meaning |
|---|---|---|
| `PAYLOAD_DRILL` | `0` | `1` = drill fitted: GPIO13 servo set up, `/drill` works |
| `PAYLOAD_DRILL_AUTO` | `0` | `1` (with `PAYLOAD_DRILL=1`) = drill runs automatically when gauge pressure averages < 2 bar |
| `PAYLOAD_IMAGE_DIR` | `~/DCIM` | where `/capture` (and auto-save) save images |
| `PAYLOAD_AUTOSAVE` | `0` | `1` = the detector saves an annotated frame (max every 4 s) while anything is detected |
| `PAYLOAD_ROBOT_HOST` | `huntsman.local` | robot console host (dashboard driving) |
| `PAYLOAD_ROBOT_PORT` | `23` | robot console port |

`/update` runs `deploy.sh` from the repo root if one exists.

Open http://arachnid.local:8080 (or http://192.168.0.162:8080).
