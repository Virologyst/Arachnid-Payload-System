# Raspberry Pi 5 setup

Fresh Pi 5 -> payload running. This is what was done on the current Pi (2026-10-16).

| | |
|---|---|
| Hostname / IP | `arachnid` / 192.168.0.162 (DHCP - reserve it in the router) |
| User | `virologyst` (passwordless sudo) |
| OS | Raspberry Pi OS 64-bit, **Debian 13 Trixie**, kernel 6.18, Python 3.13 |
| Hardware | Pi 5 8 GB, 256 GB SD card |
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
- On this Pi only the hostname carried over - SSH, the key and Wi-Fi had to be set by hand. Check after the
  first boot.

## 3. SSH access (if the key didn't carry over)

**Gotcha:** Trixie images use cloud-init, which writes `/etc/ssh/sshd_config.d/50-cloud-init.conf` with
`PasswordAuthentication no`, and the stock `sshd_config` has `PubkeyAuthentication no`. sshd uses the
**first** value it reads, and `sshd_config.d/*.conf` is read first, in name order - so a `00-*.conf` file
decides. Check the result with `sudo sshd -T | grep -i authentication`.

On the Pi (keyboard/screen), add the PC's key:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "<contents of id_ed25519.pub>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

and make SSH keys-only:

```bash
printf "PubkeyAuthentication yes\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n" | sudo tee /etc/ssh/sshd_config.d/00-auth.conf
sudo systemctl reload ssh
```

## 4. System

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-dev i2c-tools nodejs npm   # Trixie's nodejs is 20.19 - enough for Vite 7
sudo raspi-config nonint do_i2c 0      # Enviro+ sensors
sudo raspi-config nonint do_spi 0      # Enviro+ LCD
```

Power check, any time: `vcgencmd get_throttled` should print `throttled=0x0`. Anything else means
undervoltage or overheating.

Only with a supply that really gives 5 A: add `usb_max_current_enable=1` to `/boot/firmware/config.txt`
(otherwise the Pi 5 limits USB to 600 mA total - the OAK can brown out).

Enviro+ check: `i2cdetect -y 1` should show 0x23 (LTR559), 0x49 (ADS1015 gas) and 0x76 (BME280).

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
won't install cleanly. Installed as of 2026-10-16: depthai 3.11.0, depthai-nodes 0.3.7.

## 7. Dashboard (web UI)

```bash
cd ~/Arachnid-Payload-System/interface && npm install && npm run build
cd .. && rm -rf static && cp -r interface/build static
```

## 8. Run

```bash
cd ~/Arachnid-Payload-System && source .venv/bin/activate && python app.py
```

The app starts without the OAK (dummy detections - a colour-cycling test image) or the Enviro+
(`/enviro` returns 503). The startup log says which hardware it found.

| Environment variable | Default | Meaning |
|---|---|---|
| `PAYLOAD_DRILL` | `0` | `1` = drill fitted: GPIO13 servo set up, `/drill` works |
| `PAYLOAD_DRILL_AUTO` | `0` | `1` (with `PAYLOAD_DRILL=1`) = drill runs automatically when gauge pressure averages < 2 bar |
| `PAYLOAD_IMAGE_DIR` | `~/DCIM` | where `/capture` saves images |
| `PAYLOAD_ROBOT_HOST` | `huntsman.local` | robot console host (dashboard driving) |
| `PAYLOAD_ROBOT_PORT` | `23` | robot console port |

`/update` runs `deploy.sh` from the repo root if one exists.

Open http://arachnid.local:8080 (or http://192.168.0.162:8080).
