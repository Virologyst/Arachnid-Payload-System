# The host robot: Huntsman

This payload rides on **Huntsman**, an 8-legged load-carrying spider robot. This file is a payload-focused
summary. The robot project is the source of truth - check it for anything newer:

- Local: `C:\Users\craig\CLionProjects\Huntsman` - read its `CONTEXT.md` first, then `docs/`
- GitHub: https://github.com/Virologyst/Project-Huntsman

_Summary taken from Huntsman `CONTEXT.md` dated 2026-10-16._

**Status:** prototype 1 finished and parked (git tag `prototype-1`, 2026-10-13). **Prototype 2 is being
built** (more X clearance, 75 kg.cm Y servos, bigger 8.5 V regulator, foot pressure + body tilt sensors) -
expect a new joint map and changed gait constants when it walks again.

## Body and motion

- 8 legs x 3 joints = 24 servos (~55 kg, 270 deg, 0.5-2.5 ms), fed 8.5 V. Joints: **X** = swing (coxa),
  **Y** = lift (femur), **K** = knee. Legs: `FL FML BML BL` (left), `FR FMR BMR BR` (right).
- Controller: ESP32-S3 in the "Brain Box" with 2x PCA9685 (0x40 left, 0x41 right) on its I2C bus (GPIO8/9).
  The payload must **not** share that I2C bus.
- Gait: hexapod-style alternating tetrapod (4 feet always down), joint space (IK in the code, off). Expect the body
  to **bob, sway and lower** while walking (walk pose is lower than stand). Camera mounts need to cope
  with vibration and tilt; image stabilisation / motion blur matters.
- Body height/tilt control is planned (needs IK) - not available yet.
- **Obstacle stop:** a forward VL53L0X time-of-flight sensor slows forward walking from 400 mm and stops it
  at 100 mm (`Obstacle at N mm - holding`); `climb` (or LT) carries on. Back / turn still work.
- **Xbox controller** (BLE) can also drive it: stick release pauses in place; A = stand pose, B = sit.

## Power

- Battery: Makita 18 V 6 Ah (~108 Wh), mounted centrally. No built-in low-voltage cutoff
  (Makita packs rely on the tool) - a cutoff is still an open item on the robot.
- Rails: 18 V -> 8.5 V servo feed (servos draw 15-25 A walking, big spikes; stalls pull it down for
  hundreds of ms) and a 5 V buck for the ESP32 fed from the 18 V side.
- **The payload gets its own regulator** (see CONTEXT.md, "Power"). Never power the Pi from the ESP32's
  USB port or 5 V buck.

## Talking to the robot

The robot is on Wi-Fi as **`huntsman.local`** (seen at 192.168.0.108 on the home network). It also knows a
second network (`WIFI_SSID_2`) - intended to be the **Pi's hotspot** for use in the field.

- **Console:** raw TCP on **port 23**. Same text console as USB: send a line ending in `\n`, read text back.
- **One client at a time** - a new connection replaces the old one. If the payload holds the connection,
  the developer's PlatformIO monitor gets kicked off (and vice versa).
- **Any byte received aborts a move** and holds position (walks finish their current step, then return
  to stand). The payload must not send anything mid-move unless it means "stop".
- Long commands (`walk`, `stand`, prompts) **block** the robot's loop until they finish; output is
  human-readable text, not a structured protocol.
- Useful commands:

  | Command | Effect |
  |---|---|
  | `status` | read-only status |
  | `map` | read-only joint map |
  | `stand` / `sit` | stand up / sit down (ramped) |
  | `walk [n]` / `back [n]` | n cycles forward / backward (no n = until any byte; then finishes the step and stands) |
  | `turn left [n]` / `turn right [n]` | turn on the spot (same stop rule) |
  | `climb [n]` | climb past an obstacle |
  | `limp` | release all servos |
  | `help` | full list |

- Robot replies the payload relies on (`robot_link.py`): `Walking ...`, `Stopped - standing.`,
  `Not in the stand pose - run 'stand' first.`, `Obstacle at N mm - holding...`, `Standing.`, `Sitting.`.
  An empty line is ignored when idle; any byte stops / aborts and **flushes** anything queued behind it.
- The payload **drives the robot** from the dashboard (`robot_link.py`, `/robot/*`) - see CONTEXT.md.
- A structured payload<->robot protocol (e.g. JSON lines, or a second TCP port) would need changes in the
  Huntsman firmware (`src/console.cpp`, `src/net.cpp`, `include/term.h`).

## Safety

- The servos are strong enough to injure. Payload code must **never send motion commands** (`stand`,
  `walk`, `turn`, `p`, `sweep`, joint moves...) while testing unless the user says the robot is clear or
  off. Read-only commands (`status`, `map`, `help`) are fine.
- OTA firmware uploads to the robot sit it down and reboot it; the console connection drops.
