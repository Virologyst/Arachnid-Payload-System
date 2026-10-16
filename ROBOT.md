# The host robot: Huntsman

This payload rides on **Huntsman**, an 8-legged load-carrying spider robot. This file is a payload-focused
summary. The robot project is the source of truth - check it for anything newer:

- Local: `C:\Users\craig\CLionProjects\Huntsman` - read its `CONTEXT.md` first, then `docs/`
- GitHub: https://github.com/Virologyst/Project-Huntsman

_Summary taken from Huntsman `CONTEXT.md` dated 2026-10-03._

## Body and motion

- 8 legs x 3 joints = 24 servos (~55 kg, 270 deg, 0.5-2.5 ms), fed 8.5 V. Joints: **X** = swing (coxa),
  **Y** = lift (femur), **K** = knee. Legs: `FL FML BML BL` (left), `FR FMR BMR BR` (right).
- Controller: ESP32-S3 in the "Brain Box" with 2x PCA9685 (0x40 left, 0x41 right) on its I2C bus (GPIO8/9).
  The payload must **not** share that I2C bus.
- Gait: joint-space alternating tetrapod (4 feet always down), no inverse kinematics yet. Expect the body
  to **bob, sway and lower** while walking (walk pose is lower than stand). Camera mounts need to cope
  with vibration and tilt; image stabilisation / motion blur matters.
- Body height/tilt control is planned (needs IK) - not available yet.

## Power

- Battery: Makita 18 V 5.0 Ah (~90 Wh), mounted off-centre on one side. No built-in low-voltage cutoff
  (Makita packs rely on the tool) - a cutoff is still an open item on the robot.
- Rails: 18 V -> 8.5 V servo feed (servos draw 15-25 A walking, with big current spikes) and an 8.5 V ->
  5 V buck that powers the ESP32 only.
- **The payload gets its own regulator** (see CONTEXT.md, "Power"). Never power the Pi from the ESP32's
  USB port or 5 V buck.

## Talking to the robot

The robot is on Wi-Fi as **`huntsman.local`** (seen at 192.168.0.108 on the home network).

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
  | `walk [n]` / `back [n]` | n cycles forward / backward (no n = until a key) |
  | `turn left` / `turn right` | turn on the spot |
  | `limp` | release all servos |
  | `help` | full list |

- The payload is expected to **control the robot in future** - see CONTEXT.md for how the code allows for it.
- A structured payload<->robot protocol (e.g. JSON lines, or a second TCP port) would need changes in the
  Huntsman firmware (`src/console.cpp`, `src/net.cpp`, `include/term.h`).

## Safety

- The servos are strong enough to injure. Payload code must **never send motion commands** (`stand`,
  `walk`, `turn`, `p`, `sweep`, joint moves...) while testing unless the user says the robot is clear or
  off. Read-only commands (`status`, `map`, `help`) are fine.
- OTA firmware uploads to the robot sit it down and reboot it; the console connection drops.
