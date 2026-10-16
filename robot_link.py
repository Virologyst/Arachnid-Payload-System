"""Link to the Huntsman robot's Wi-Fi console (raw TCP, huntsman.local:23) - see ROBOT.md.

The robot takes one console client at a time, so the link only holds the connection while armed
(disarming frees it for the PlatformIO monitor). Any byte the robot receives stops a walk after the
current step and aborts stand/sit, and it flushes whatever else was queued - so a new command is only
sent once the robot reports it has stopped.

Driving is hold-to-move: the browser calls drive() repeatedly while a key is held; if those calls stop
for HEARTBEAT_TIMEOUT_S (key released, tab hidden, network gone) the watchdog sends stop.
"""
import socket
import threading
import time
from collections import deque

DRIVE_COMMANDS = {"forward": "walk", "back": "back", "left": "turn left", "right": "turn right"}
POSE_COMMANDS = {"stand": "stand", "sit": "sit"}

HEARTBEAT_TIMEOUT_S = 0.7
STOP_WAIT_S = 6.0           # finish the current step + return to the stand pose
POSE_TIMEOUT_S = 15.0

# Robot console lines that mean "idle again" (motion.cpp)
_DRIVE_DONE = ("Stopped", "Not in the stand pose", "Obstacle at", "Paused")
_POSE_DONE = ("Standing.", "Sitting.")


class RobotLink:
    def __init__(self, host: str, port: int = 23, log=None):
        self.host = host
        self.port = port
        self.log = log or (lambda msg: None)
        self.lines = deque(maxlen=200)    # recent robot console output
        self.armed = False
        self.moving = None                # drive direction while walking / turning
        self.pose_busy = False
        self._sock = None
        self._lock = threading.RLock()
        self._idle = threading.Event()
        self._idle.set()
        self._busy_since = 0.0
        self._last_beat = 0.0
        self._pending = None              # direction waiting for the robot to stop
        threading.Thread(target=self._watchdog, daemon=True).start()

    # ---------- connection ----------

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def arm(self) -> None:
        with self._lock:
            if not self.connected:
                sock = socket.create_connection((self.host, self.port), timeout=3)
                sock.settimeout(None)
                self._sock = sock
                threading.Thread(target=self._reader, args=(sock,), daemon=True).start()
                self.log(f"Robot console connected: {self.host}:{self.port}")
            self.armed = True

    def disarm(self) -> None:
        with self._lock:
            self.stop()
            self.armed = False
            self._close()

    def _close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
            self.log("Robot console disconnected")
        self.moving = None
        self.pose_busy = False
        self._idle.set()

    def _send(self, text: str) -> None:
        if self._sock is None:
            raise RuntimeError("Robot not connected")
        try:
            self._sock.sendall(text.encode())
        except OSError as e:
            self._close()
            self.armed = False
            raise RuntimeError(f"Robot connection lost: {e}")

    def _reader(self, sock) -> None:
        buf = b""
        while True:
            try:
                data = sock.recv(1024)
            except OSError:
                data = b""
            if not data:
                break
            buf += data
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode(errors="replace").strip()
                if line:
                    self._on_line(line)
        with self._lock:
            if self._sock is sock:   # dropped by the robot, not by us
                self._close()
                self.armed = False

    def _on_line(self, line: str) -> None:
        self.lines.append(f"{time.strftime('%H:%M:%S')} {line}")
        if line.startswith(_DRIVE_DONE) or line.startswith(_POSE_DONE):
            self.moving = None
            self.pose_busy = False
            self._idle.set()

    # ---------- commands ----------

    def _wait_idle(self, timeout: float) -> bool:
        return self._idle.wait(timeout)

    def stop(self) -> None:
        """Always allowed. Any byte stops a walk after the current step (an idle robot ignores an empty line)."""
        with self._lock:
            if self.connected and (self.moving or self.pose_busy):
                self._send("\n")
                self.log("Robot: stop")
                self._busy_since = time.monotonic()   # time-out counts from the stop
            self._last_beat = 0.0
            self._pending = None

    def drive(self, direction: str) -> None:
        if direction not in DRIVE_COMMANDS:
            raise ValueError(f"Unknown direction '{direction}'")
        with self._lock:
            if not self.armed:
                raise PermissionError("Robot control is not armed")
            if self.pose_busy:
                raise RuntimeError("Robot is changing pose - wait for it to finish")
            self._last_beat = time.monotonic()
            if self.moving == direction or self._pending == direction:
                return        # heartbeat only
            if self.moving:   # change of direction: stop, wait for "Stopped", then the new command
                self.stop()
                self._last_beat = time.monotonic()
            self._pending = direction
        if not self._wait_idle(STOP_WAIT_S):
            raise RuntimeError("Robot did not report stopping")
        with self._lock:
            if not self.armed or self._pending != direction:   # disarmed, stopped or re-steered while waiting
                return
            self._pending = None
            self._idle.clear()
            self._busy_since = time.monotonic()
            self.moving = direction
            self._send(DRIVE_COMMANDS[direction] + "\n")
            self.log(f"Robot: {DRIVE_COMMANDS[direction]}")

    def pose(self, name: str) -> None:
        if name not in POSE_COMMANDS:
            raise ValueError(f"Unknown pose '{name}'")
        with self._lock:
            if not self.armed:
                raise PermissionError("Robot control is not armed")
            if self.moving or self.pose_busy:
                raise RuntimeError("Robot is busy - stop first")
            self._idle.clear()
            self._busy_since = time.monotonic()
            self.pose_busy = True
            self._send(POSE_COMMANDS[name] + "\n")
            self.log(f"Robot: {POSE_COMMANDS[name]}")

    def _watchdog(self) -> None:
        while True:
            time.sleep(0.1)
            try:
                with self._lock:
                    now = time.monotonic()
                    if self.moving and self._last_beat and now - self._last_beat > HEARTBEAT_TIMEOUT_S:
                        self.log("Robot: no heartbeat from the browser - stopping")
                        self.stop()
                    # Never heard a "done" line: don't stay busy for ever
                    if (self.moving or self.pose_busy) and not self._last_beat and \
                            now - self._busy_since > max(STOP_WAIT_S, POSE_TIMEOUT_S):
                        self.moving = None
                        self.pose_busy = False
                        self._idle.set()
            except Exception as e:
                self.log(f"Robot watchdog error: {e}")

    def state(self) -> dict:
        return {
            "host": f"{self.host}:{self.port}",
            "armed": self.armed,
            "connected": self.connected,
            "moving": self.moving,
            "pose_busy": self.pose_busy,
            "lines": list(self.lines)[-30:],
        }
