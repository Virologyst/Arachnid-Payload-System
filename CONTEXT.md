# Huntsman Payload - Project Context

Living summary of what this project is, what has been decided and why, and where it is up to.
**Keep this file current.**

_Last updated: 2026-10-04_

## What it is

The **Arachnid Payload System** - a Raspberry Pi sensing and inspection payload (camera detection,
environmental sensing, drill) - being adapted to ride on the **Huntsman** spider robot ([ROBOT.md](ROBOT.md)).
Repo: https://github.com/Virologyst/Arachnid-Payload-System (the user's own; `origin`). It began as the
EGH455 project; [README.md](README.md) describes the system as built there.

## Hardware

| Part | Detail |
|---|---|
| Computer | **Raspberry Pi 5** (Raspberry Pi OS Bookworm; GPIO via lgpio / gpiozero) |
| Camera | **Luxonis OAK-D Lite** (DepthAI v3, RVC2, USB-C) - located 2026-10-16, so the existing DepthAI code is used as is. Backup: Freenove 8MP CSI camera (IMX219, 120 deg, Pi 5 cable), which would need CPU inference (picamera2 + ONNX) |
| Sensors | Pimoroni **Enviro+** HAT (BME280, LTR559, gas, ST7735 LCD) - **staying** |
| Drill | Continuous-rotation servo on GPIO13 - **not fitted for now**, a drill attachment may come later |
| Power | Own 5 V / 5 A buck from the robot's 18 V battery (see "Power") |

## What the software does (as inherited)

See [README.md](README.md) for the full API. In short: `app.py` is a Flask server on port 8080 with the
annotated MJPEG stream, detections (valves, gauges -> pressure, ArUco), Enviro+ readings logged to SQLite,
LCD modes, image capture, the drill, logs and status; it serves the SvelteKit dashboard in `interface/`.

## Key decisions (and why)

- **Separate project from the robot firmware** - different language, device and release cycle; robot
  knowledge lives in [ROBOT.md](ROBOT.md) plus a pointer to the Huntsman repo.
- **Enviro+ stays**; Enviro+ code stays as is.
- **Drill code is kept but must be disabled by default** - no drill is fitted yet, but one may be added
  later. The inherited code **auto-runs the drill when gauge pressure averages below 2 bar**; on a robot that
  must become an explicit, opt-in action. Keep the drill behind a clear "attachment present / enabled" switch.
- **Design for controlling the robot later** (user, 2026-10-04). Even before the payload sends any motion
  commands, structure the code so that's a small step:
  - One **robot-link module** owns the single console connection to huntsman.local:23 (the robot allows one
    client), reconnects, and exposes robot state (`status`) to the rest of the app and the dashboard.
  - All commands go through that module: one place for an **enable switch** (motion off by default),
    a **stop** that's always allowed, and logging of every command sent.
  - Never send bytes during a move except to stop (any byte aborts a move on the robot).
  - The text console is fine to start; a structured protocol (JSON lines or a second port) would be a
    Huntsman firmware change - plan it on both sides when control becomes real.
- **Dashboard drives the robot (built 2026-10-16, user request): hold-to-move with a dead-man watchdog.**
  `robot_link.py` + `/robot`, `/robot/arm`, `/robot/drive`, `/robot/stop`, `/robot/pose`; UI in
  `interface/src/lib/RobotControl.svelte`. Why this shape:
  - **Arm toggle** (off on every page load) connects to the console; disarm disconnects, freeing it for
    the PlatformIO monitor (one client only).
  - Hold an arrow key / pad button -> `walk` / `back` / `turn left|right` (no count = until a byte).
    The browser re-sends the direction every 200 ms; **no heartbeat for 700 ms -> stop** (key up, tab
    hidden, window blur, network loss). Space / Esc / STOP always stop.
  - The robot flushes input on a stop, so a change of direction sends stop, waits for `Stopped`, then the
    new command; drive is refused while `stand` / `sit` run (any byte would abort them).
  - Tested against a fake console (localhost); **not yet on the real robot**.

## Power (proposed, not built)

- The ESP32 dev board's USB port is a power **input** (CH340 serial), and its 5 V buck is sized for the
  ESP32 only - neither can supply the Pi.
- Load: Pi 5 ~3-8 W (wants 5 V / 5 A for full USB current), OAK ~2.5-5 W, Enviro+ small -> **5 V, 5 A** buck.
- On the bench the official 27 W supply negotiates 5 A, so USB gets 1.6 A automatically. A buck converter
  can't negotiate, so on the robot `usb_max_current_enable=1` **must** be in `/boot/firmware/config.txt`
  or the OAK gets 600 mA and browns out.
- Feed it straight from the **18 V battery** (wide-input buck, e.g. 9-36 V in), fused - not from the
  8.5 V servo rail (spikes, sag). Common ground with the robot is fine; isolation isn't needed.
- Set `usb_max_current_enable=1` in `/boot/firmware/config.txt` only if the buck really gives 5 A;
  otherwise the Pi 5 limits USB to 600 mA total.
- A future drill servo must **not** run from the Pi's 5 V pins - give it its own supply.
- Plan a clean shutdown before the battery is pulled / hits cutoff (SD card corruption).

## Current status

- [x] Repo cloned to `C:\Users\craig\PycharmProjects\Huntsman-Payload`; robot context written (ROBOT.md)
- [x] Camera: OAK-D Lite on hand (2026-10-16)
- [x] Pi 5 set up (2026-10-16): Trixie, `arachnid` / 192.168.0.162, user `virologyst`, key SSH from the dev PC,
      I2C + SPI on, OAK udev rule, repo cloned, venv (depthai 3.11), dashboard built
      ([docs/pi-setup.md](docs/pi-setup.md))
- [ ] Pi SSH keys-only (`00-auth.conf`) - user to apply (security setting)
- [x] First run on the Pi (2026-10-16) without OAK or Enviro+: dashboard, MJPEG stream (dummy), `/targets`,
      `/capture` work. OAK and Enviro+ are optional (dummy detector / 503); fixed the stale dummy detector
- [x] Hard-coded EGH455 paths removed (`PAYLOAD_IMAGE_DIR`, default `~/DCIM`; `/update` uses repo `deploy.sh`)
- [x] Drill off by default: `PAYLOAD_DRILL=1` enables it, `PAYLOAD_DRILL_AUTO=1` the < 2 bar auto-drill
- [x] depthai-nodes pinned to 0.3.7 (`ImgDetectionsBridge` removed in 0.5, its `setLabelEncoding` in 0.4)
- [x] OAK-D Lite running on the Pi (2026-10-16), USB 3 (5 Gbps), real detection pipeline - earlier cables were
      charge-only
- [ ] Enviro+ LCD on the Pi 5: with SPI on, the ST7735 driver couldn't claim GPIO9 (DC pin, also SPI0
      MISO) - check when the Enviro+ is fitted (Pimoroni's Pi 5 notes)
- [x] Payload on battery power (2026-10-16): `usb_max_current_enable=1` set - without it the OAK reset every
      ~4 s (600 mA USB limit). Supply reads 4.96-4.99 V - turn the buck up to 5.1-5.2 V
- [x] Starts on boot: systemd `payload.service` (`deploy/payload.service`)
- [ ] Backup: Luxonis OAK Y-adapter (powers the OAK separately) - no AU stockist found; Luxonis shop / Arducam
- [ ] Payload power supply final build (5 V / 5 A buck from 18 V, set 5.1-5.2 V; Pi peak ~2.5 A + OAK ~1 A); mount on the robot
- [ ] Trim `requirements.txt` (currently a full system `pip freeze`)
- [x] Robot control from the dashboard (arrow keys, stand/sit, stop) - fake-console tested 2026-10-16
- [ ] First drive of the real robot from the dashboard (user present, robot clear, legs-up first)
- [x] Dashboard title: "Project Arachnid: Huntsman PL01 - Ultrasonic Thickness"
- [ ] Check video and detection while the robot walks (vibration, motion blur)

## Open questions

- Robot control beyond the dashboard (detection-driven moves)? Structured protocol / second console port on Huntsman?

## Next step

First real drive from the dashboard (robot on its stand or area clear); buck voltage to 5.1-5.2 V.
