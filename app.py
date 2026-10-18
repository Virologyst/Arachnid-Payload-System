# ───── Standard Library ─────
import os
import time
import datetime
from collections import deque
import logging
import subprocess
import random
import socket
import smbus2
import sys
import cv2
from threading import Thread, Lock
from collections import deque

# ───── Third-Party ─────
import cv2
import depthai as dai

import sqlite3
from flask import (
    Flask, Response, jsonify,
    send_from_directory, render_template_string,
    send_file, request, redirect
)

from target_detection.interface import TargetDetectionDummy
from target_detection.inference import TargetDetection
from robot_link import RobotLink

# --- Enviro+ sensors ---
from smbus2 import SMBus
from enviroplus import gas
from bme280 import BME280
from ltr559 import LTR559
from subprocess import PIPE, Popen
import colorsys

# --- Enviro LCD  ---
from fonts.ttf import RobotoMedium as UserFont
from PIL import Image, ImageDraw, ImageFont
import st7735

# --- Drill service (Nicky) ---
# Import Libraries needed to run code
from gpiozero import AngularServo
from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

Device.pin_factory = LGPIOFactory()
sys.stdout.reconfigure(line_buffering=True)

# import curses
# from time import sleep

# ───── App Setup ─────
app = Flask(__name__, static_folder="static", static_url_path="")

# ───── Payload config (environment variables) ─────
# Drill is off unless an attachment is fitted. PAYLOAD_DRILL=1 enables /drill;
# PAYLOAD_DRILL_AUTO=1 also runs it automatically when gauge pressure averages below 2 bar.
DRILL_ENABLED = os.environ.get("PAYLOAD_DRILL", "0") == "1"
DRILL_AUTO = DRILL_ENABLED and os.environ.get("PAYLOAD_DRILL_AUTO", "0") == "1"
IMAGE_DIR = os.path.expanduser(os.environ.get("PAYLOAD_IMAGE_DIR", "~/DCIM"))
ROBOT_HOST = os.environ.get("PAYLOAD_ROBOT_HOST", "huntsman.local")
ROBOT_PORT = int(os.environ.get("PAYLOAD_ROBOT_PORT", "23"))

# ───── Captive portal (hotspot) ─────
# On the hotspot every DNS name resolves to the Pi (deploy/hotspot). A phone joining it fetches a known URL
# (connectivitycheck.gstatic.com, captive.apple.com, msftconnecttest.com...) to test for internet; answering
# that with a redirect makes the OS open the dashboard as a "sign in to network" page.
HOTSPOT_IP = "10.42.0.1"
OWN_HOSTS = {"localhost", "arachnid", "arachnid.local", socket.gethostname(), socket.gethostname() + ".local"}

@app.before_request
def captive_portal():
    host = request.host.split(":")[0].lower()
    if host in OWN_HOSTS or host.replace(".", "").isdigit():   # our names, or any IP address
        return None
    print(f"Captive portal: {request.remote_addr} asked for {host}{request.path} - redirecting", flush=True)
    return redirect(f"http://{HOTSPOT_IP}:8080/", code=302)

DEPLOY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy.sh")

# ───── Logging Setup ─────
from collections import deque
import logging

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "egh455.log")

LOG_BUFFER = deque(maxlen=1000)

# Load existing logs from main log file on start
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()[-1000:]  # only keep latest 1000 lines
        for line in lines:
            line = line.replace("\0", "").strip()   # power loss mid-write leaves NUL runs in the file
            if line:
                LOG_BUFFER.append(line)

class FrontendBufferHandler(logging.Handler):
    def emit(self, record):
        LOG_BUFFER.append(self.format(record))

# St format
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# File handler (persistent logs)
# file_handler = logging.FileHandler(LOG_FILE)
file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setFormatter(formatter)
buffer_handler = FrontendBufferHandler()
buffer_handler.setFormatter(formatter)

# Attach
logging.getLogger('werkzeug').setLevel(logging.ERROR)
app.logger.addHandler(file_handler)
app.logger.addHandler(buffer_handler)
app.logger.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.addHandler(buffer_handler)
app.logger.propagate = False

# Initialize detection system (falls back to the dummy if no OAK camera is connected)
try:
    target_system = TargetDetection(LOG_BUFFER)
    CAMERA_OK = True
    print("Initialized target system", flush=True)
except Exception as e:
    target_system = TargetDetectionDummy(LOG_BUFFER)
    CAMERA_OK = False
    print(f"OAK camera not available ({e}) - using dummy detections", flush=True)

target_system.start()

def camera_retry_thread():
    """At boot the OAK can still be enumerating when the app starts. Keep trying and swap the real
    camera in for the dummy once it answers (every user of target_system reads the global each time)."""
    global target_system, CAMERA_OK
    while not CAMERA_OK:
        time.sleep(5)
        try:
            real = TargetDetection(LOG_BUFFER)
            real.start()
        except Exception:
            continue
        dummy, target_system, CAMERA_OK = target_system, real, True
        dummy.stop()
        print("OAK camera connected - live detections", flush=True)

if not CAMERA_OK:
    Thread(target=camera_retry_thread, daemon=True).start()

# ──────────────── Drilling Mechanism (Nicky) ────────────────

# detections = target_system.get_gauge_pressure()
# Note to Nicky - pressure plate detection target_system.get_gauge_pressure() - Lower limit 2 Bar. Needs low pass filter
time.sleep(1)

# Initialize Servo (GPIO pin 13) - only when a drill is fitted
servo = None
if DRILL_ENABLED:
    servo = AngularServo(
        13,
        min_angle=0, max_angle=360,
        min_pulse_width=0.001, max_pulse_width=0.002,
        initial_angle=None      # <- do nothing on construction
    )

def drill_sequence():
    if servo is None:
        raise RuntimeError("Drill disabled (set PAYLOAD_DRILL=1 when a drill is fitted)")
    try:
        print("Starting drill sequence...")
        servo.value = +1.0     # full speed
        time.sleep(28)
        servo.value = -1.0     # reverse (if desired)
        time.sleep(28)
        servo.value = 0.0      # stop (still holding)
        time.sleep(0.5)
    finally:
        servo.detach()         # ensure it really stops on exit/errors
        print("Drill sequence completed.")

def drill_loop_thread():
    """ Thread for drill that constantly averages pressure guage readings
        Commences drilling once pressure guage is under threshold (2 bar)"""

    # Parameters
    MOVING_AVG_WINDOW = 10
    PRESSURE_THRESHOLD = 2
    READ_DELAY = 0.1

    pressure_window = deque(maxlen=MOVING_AVG_WINDOW)

    while True:
        # Read pressure gauge
        pressure = target_system.get_gauge_pressure()
        if pressure is None:
            #print("No Pressure Reading")
            time.sleep(READ_DELAY)
            continue
        
        # Store in rolling window
        pressure_window.append(pressure)

        # Compute moving average
        avg_pressure = sum(pressure_window) / len(pressure_window)

        print(f"Pressure: {pressure:.2f} bar | Avg: {avg_pressure:.2f} bar")

        # Check threshold condition
        if len(pressure_window) == MOVING_AVG_WINDOW and avg_pressure < PRESSURE_THRESHOLD:
            print("✅ Pressure below threshold — commence drilling!")
            drill_sequence()
        else:
            print("⏳ Waiting for pressure to drop...")

        time.sleep(READ_DELAY)

# Start Drill Thread (auto-drill is opt-in)
if DRILL_AUTO:
    Thread(target=drill_loop_thread, daemon=True).start()
print(f"Drill: {'enabled' if DRILL_ENABLED else 'disabled'}, auto: {'on' if DRILL_AUTO else 'off'}", flush=True)

# ──────────────── Get IP ────────────────
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "No IP"
    finally:
        s.close()
    return ip

# ──────────────── ENVIRO+ SENSORS AND LCD ────────────────

time.sleep(1.0)  # Give it a sec

# Initialise sensors (Same as examples) - the payload still runs if the Enviro+ isn't fitted
try:
    bme280 = BME280()
    bme280.get_temperature()
    ltr559 = LTR559()
    ENVIRO_OK = True
except Exception as e:
    bme280 = ltr559 = None
    ENVIRO_OK = False
    print(f"Enviro+ not detected ({e}) - sensor readings disabled", flush=True)
gas_sensor = gas

disp = None
try:
    if not ENVIRO_OK:
        raise RuntimeError("Enviro+ not detected")

    disp = st7735.ST7735(
        port=0,
        cs=1,
        dc="GPIO9",
        backlight="GPIO12",
        rotation=270,
        spi_speed_hz=10000000
    )

    # Initialize display.
    disp.begin()

    print("Enviro+ and LCD initialised correctly.")

except (Exception, SystemExit) as e:   # gpiodevice calls sys.exit() when a pin is busy
    print("LCD init failed:", e)
    disp = None


# ──────────────── DATABASE SETUP ────────────────
DB_PATH = 'database/egh455.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # makes results dict-like
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Enviro+ sensor data
    cur.execute("""
        CREATE TABLE IF NOT EXISTS enviro_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL,
            humidity REAL,
            pressure REAL,
            oxidising REAL,
            reducing REAL,
            nh3 REAL,
            lux REAL,
            proximity INTEGER
        )
    """)

    # System status / flags
    cur.execute("""
        CREATE TABLE IF NOT EXISTS status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# ──────────────── TARGET DETECTION INTEGRATION (Oliver) ────────────────

def gen_frames():
    """Generate MJPEG frames using the active detection system."""
    global target_system
    while True:
        target_system.wait_for_new_image(timeout=1.0)
        frame_bytes = target_system.get_image_bytes()
        if frame_bytes:

            yield frame_bytes


# # ──────────────── DEPTHAI CAMERA ────────────────

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

@app.route("/capture", methods=["POST"])
def capture_image():
    """Capture a single frame from DepthAI and save it."""
    try:

        frame = target_system.get_image_bytes(encode=False)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{IMAGE_DIR}/capture_{timestamp}.jpg"

        cv2.imwrite(filename, frame)
        return jsonify({"status": "ok", "file": filename})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/images")
def list_images():
    """Return JSON list of saved images (latest 10 first)."""
    files = sorted(
        [f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg")],
        key=lambda x: os.path.getmtime(os.path.join(IMAGE_DIR, x)),
        reverse=True
    )
    latest = files[:10]
    return jsonify({"images": latest})


@app.route("/images/<filename>")
def get_image(filename):
    """Serve a specific saved image."""
    return send_file(os.path.join(IMAGE_DIR, filename), mimetype="image/jpeg")


@app.route("/images/delete/<filename>", methods=["DELETE"])
def delete_image(filename):
    """Delete an image from the folder."""
    try:
        os.remove(os.path.join(IMAGE_DIR, filename))
        return jsonify({"status": "ok", "message": f"{filename} deleted"})
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File not found"}), 404

# ──────────────── LCD CONTROL ROUTES (Charlie)  ────────────────
MODE_IP, MODE_DET, MODE_TEMP = 0, 1, 2
_mode = MODE_IP
_mode_lock = Lock()

def set_mode(m: int) -> None:
    global _mode
    with _mode_lock:
        _mode = m

def get_mode() -> int:
    with _mode_lock:
        return _mode

lcd_loop_active = True
current_mode = "ip"

@app.route("/lcd/on", methods=["POST"])
def lcd_on():
    """Turn the LCD backlight ON."""
    try:
        disp.set_backlight(True)
        return jsonify({"status": "ok", "message": "LCD backlight turned on"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/lcd/off", methods=["POST"])
def lcd_off():
    """Turn the LCD backlight OFF."""
    try:
        disp.set_backlight(False)
        return jsonify({"status": "ok", "message": "LCD backlight turned off"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/lcd/show/ip", methods=["POST"])
def lcd_show_ip():
    """Show IP Address"""
    set_mode(MODE_IP)
    return jsonify(ok=True, mode="ip")
    
@app.route("/lcd/show/liveDetections", methods=["POST"])
def liveDetections_show():
    """Show Live Detections"""
    set_mode(MODE_DET)
    return jsonify(ok=True, mode="liveDetections")

@app.route("/lcd/show/temperature", methods=["POST"])
def liveTemperatures_show():
    """Show Live Temperatures"""
    set_mode(MODE_TEMP)
    return jsonify(ok=True, mode="temperature")

# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    process = Popen(["/usr/bin/vcgencmd", "measure_temp"], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index("=") + 1:output.rindex("'")])

def lcd_loop_thread():
    """Cycle through sensor values automatically."""

    # Displays data and text on the 0.96" LCD
    def display_text(variable, data, unit):
        # Maintain length of list
        values[variable] = values[variable][1:] + [data]
        # Scale the values for the variable between 0 and 1
        vmin = min(values[variable])
        vmax = max(values[variable])
        colours = [(v - vmin + 1) / (vmax - vmin + 1) for v in values[variable]]
        # Format the variable name and value
        message = f"{variable[:4]}: {data:.1f} {unit}"
        logging.info(message)
        draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))
        for i in range(len(colours)):
            # Convert the values to colours from red to blue
            colour = (1.0 - colours[i]) * 0.6
            r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour, 1.0, 1.0)]
            # Draw a 1-pixel wide rectangle of colour
            draw.rectangle((i, top_pos, i + 1, HEIGHT), (r, g, b))
            # Draw a line graph in black
            line_y = HEIGHT - (top_pos + (colours[i] * (HEIGHT - top_pos))) + top_pos
            draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))
        # Write the text at the top in black
        draw.text((0, 0), message, font=font, fill=(0, 0, 0))
        disp.display(img)

    WIDTH = disp.width
    HEIGHT = disp.height

    # Set up canvas and font
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = 20
    font = ImageFont.truetype(UserFont, font_size)

    message = ""

    # The position of the top bar
    top_pos = 25

    # temperature down, and increase to adjust up
    factor = 2.25

    cpu_temps = [get_cpu_temperature()] * 5

    delay = 0.5  # Debounce the proximity tap
    last_page = 0
    light = 1

    # Create a values dict to store the data
    variables = ["ip-address",
                "target-detections",
                "temperature"]

    values = {}
    for v in variables:
        values[v] = [1] * WIDTH

    # The main loop
    try:
        while True:
            proximity = ltr559.get_proximity() if ENVIRO_OK else 0
            mode = get_mode()

            # If the proximity crosses the threshold, toggle the mode
            if proximity > 1500 and time.time() - last_page > delay:
                # Cycle to next mode safely
                next_mode = (mode + 1) % len(variables)
                set_mode(next_mode)
                last_page = time.time()
                mode = next_mode  # reflect immediately

            # ========== MODE 0: IP ==========
            if mode == MODE_IP:
                ip = get_ip()

                WIDTH, HEIGHT = disp.width, disp.height
                img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))  # clean background
                draw = ImageDraw.Draw(img)

                title_font = ImageFont.truetype(UserFont, 16)
                value_font = ImageFont.truetype(UserFont, 22)

                text_colour = (255, 255, 255)
                back_colour = (0, 100, 180)
                draw.rectangle((0, 0, WIDTH, HEIGHT), back_colour)

                # Title
                title = "IP ADDRESS"
                tw, th = title_font.getbbox(title)[2:]
                draw.text(((WIDTH - tw) / 2, 5), title, font=title_font, fill=text_colour)

                # IP Address
                vw, vh = value_font.getbbox(ip)[2:]
                draw.text(((WIDTH - vw) / 2, (HEIGHT / 2)), ip, font=value_font, fill=text_colour)

                disp.display(img)

            # ========== MODE 1: TARGET DETECTION IMAGE ==========
            elif mode == MODE_DET:
                # path = "test_image.jpg"
                # det_img = Image.open(path)
                detection = target_system.get_image_bytes(encode=False)  # -> np.ndarray (BGR)
                if detection is None:
                    print("No frame yet")
                else:
                    # Show the camera frame
                    # detection is np.ndarray in BGR; convert to RGB and resize to LCD
                    rgb = cv2.cvtColor(detection, cv2.COLOR_BGR2RGB)
                    frame_img = Image.fromarray(rgb)

                    # Resize to LCD resolution (keeps aspect ratio or fill; choose one)
                    WIDTH, HEIGHT = disp.width, disp.height
                    frame_img = frame_img.resize((WIDTH, HEIGHT), Image.BILINEAR)

                    disp.display(frame_img)

            # ========== MODE 2: TEMPERATURE ==========
            if mode == MODE_TEMP and ENVIRO_OK:
                # variable = "temperature"
                unit = "°C"
                cpu_temp = get_cpu_temperature()
                # Smooth out with some averaging to decrease jitter
                cpu_temps = cpu_temps[1:] + [cpu_temp]
                avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
                raw_temp = bme280.get_temperature()
                data = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
                display_text(variables[mode], data, unit)

    except Exception as e:
        print(f"[LCD LOOP ERROR] {e}")

# Start LCD Thread
if disp is not None:
    Thread(target=lcd_loop_thread, daemon=True).start()

# ──────────────── ROBOT CONTROL (Huntsman console) ────────────────
# Arm from the dashboard to connect; arrow keys drive while held; stop is always allowed.
robot = RobotLink(ROBOT_HOST, ROBOT_PORT, log=lambda msg: app.logger.info(msg))

def _robot_reply(fn):
    try:
        fn()
        return jsonify({"ok": True, **robot.state()})
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e), **robot.state()}), 403
    except (ValueError, RuntimeError, OSError) as e:
        return jsonify({"ok": False, "error": str(e), **robot.state()}), 409

@app.route("/robot")
def robot_state():
    return jsonify(robot.state())

@app.route("/robot/arm", methods=["POST"])
def robot_arm():
    armed = bool((request.get_json(silent=True) or {}).get("armed"))
    return _robot_reply(robot.arm if armed else robot.disarm)

@app.route("/robot/drive", methods=["POST"])
def robot_drive():
    direction = (request.get_json(silent=True) or {}).get("dir", "")
    return _robot_reply(lambda: robot.drive(direction))

@app.route("/robot/stop", methods=["POST"])
def robot_stop():
    return _robot_reply(robot.stop)

@app.route("/robot/pose", methods=["POST"])
def robot_pose():
    name = (request.get_json(silent=True) or {}).get("pose", "")
    return _robot_reply(lambda: robot.pose(name))

# ──────────────── ROUTES ────────────────
@app.route('/drill', methods=['POST'])
def drill_endpoint():
    try:
        drill_sequence()
        return jsonify({"status": "success", "message": "Drill activated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/logs", methods=["GET", "POST"])
def logs_endpoint():
    """GET returns combined backend logs (file + memory). POST appends new frontend entries."""
    import re

    if request.method == "GET":
        logs_list = []

        # Load logs
        try:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()[-10000:]  # 0000 lines
                for entry in lines:
                    match = re.match(r"(\d{2}:\d{2}:\d{2}),?\d*\s+\[(\w+)\]\s+(.*)", entry)
                    if match:
                        ts, lvl, msg = match.groups()
                        logs_list.append({"timestamp": ts, "type": lvl, "message": msg.strip()})
                    else:
                        logs_list.append({"timestamp": "", "type": "SYSTEM", "message": entry.strip()})
        except FileNotFoundError:
            pass

        # Merge memory buffer
        for entry in list(LOG_BUFFER):
            match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),?\d*\s+\[(\w+)\]\s+(.*)", entry)
            if match:
                ts, lvl, msg = match.groups()
                logs_list.append({"timestamp": ts, "type": lvl, "message": msg.strip()})
            else:
                logs_list.append({"timestamp": "", "type": "SYSTEM", "message": entry.strip()})

        # Return newest
        logs_list = logs_list[-10000:]
        logs_list.reverse()
        return jsonify(logs_list)

    # Handle POST
    data = request.get_json(force=True)
    msg = data.get("message", "")
    lvl = data.get("type", "SYSTEM").upper()

    log_line = f"{datetime.datetime.now():%H:%M:%S} [{lvl}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")
    LOG_BUFFER.append(log_line)

    # Force flush so it appears immediately
    for handler in app.logger.handlers:
        handler.flush()

    return jsonify({"status": "ok"})

@app.route("/")
def serve_index():
    """Serve the Svelte-built index.html."""
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static_files(path):
    """Serve static files (JS, CSS, images)."""
    return send_from_directory(app.static_folder, path)

@app.route("/video_feed")
def video_feed():
    """Stream Target feed from target_detection."""
    return Response(
        gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/enviro')
def get_enviro_data():
    """Read Enviro+ and return JSON."""
    if not ENVIRO_OK:
        return jsonify({"error": "Enviro+ not fitted"}), 503
    try:
        factor = 2.25
        cpu_temp = get_cpu_temperature()
        cpu_temps = [get_cpu_temperature()] * 5
        # Smooth out with some averaging to decrease jitter
        cpu_temps = cpu_temps[1:] + [cpu_temp]
        avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
        raw_temp = bme280.get_temperature()
        data = raw_temp - ((avg_cpu_temp - raw_temp) / factor)

        temperature = round(data, 1)
        pressure = round(bme280.get_pressure(), 1)
        humidity = round(bme280.get_humidity(), 1)

        gas_readings = gas.read_all()
        oxidising = round(gas_readings.oxidising / 1000, 3)   # kΩ
        reducing = round(gas_readings.reducing / 1000, 3)
        nh3 = round(gas_readings.nh3 / 1000, 3)

        lux = ltr559.get_lux()
        prox = ltr559.get_proximity()

        targets = target_system.get_detections()

        # --- Save to DB ---
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO enviro_data (temperature, humidity, pressure, oxidising, reducing, nh3, lux, proximity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (temperature, humidity, pressure, oxidising, reducing, nh3, lux, prox)
        )
        conn.commit()
        conn.close()

        return jsonify({
            "temperature": temperature,
            "pressure": pressure,
            "humidity": humidity,
            "oxidising": oxidising,
            "reducing": reducing,
            "nh3": nh3,
            "lux": lux,
            "proximity": prox,
            "targets": targets
        })
    except Exception as e:
        app.logger.error(f"Enviro read failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/update", methods=["POST"])
def update():
    """Trigger deploy script & restart service."""
    if not os.path.exists(DEPLOY_SCRIPT):
        return jsonify({"status": "error", "message": f"No deploy script at {DEPLOY_SCRIPT}"}), 404
    try:
        subprocess.run([DEPLOY_SCRIPT], check=True)
        return jsonify({"status": "ok", "message": "Deployment triggered"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/enviro/history")
def get_enviro_history():
    """Return last 10 minutes of enviro data from SQLite.
       If empty, generate dummy data for testing."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    ten_min_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
    cursor.execute("""
        SELECT timestamp, temperature, humidity, pressure, oxidising, reducing, nh3, lux
        FROM enviro_data
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
    """, (ten_min_ago.isoformat(),))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not rows:
        # Generate 10 minutes of fake points, one per 30s
        now = datetime.datetime.utcnow()
        rows = []
        for i in range(20):  # 20 points over 10 minutes
            ts = now - datetime.timedelta(seconds=(20 - i) * 30)
            rows.append({
                "timestamp": ts.isoformat(),
                "temperature": round(20 + random.uniform(-2, 2), 1),
                "humidity": round(50 + random.uniform(-10, 10), 1),
                "pressure": round(1013 + random.uniform(-5, 5), 1),
                "oxidising": round(random.uniform(0.5, 2.0), 3),
                "reducing": round(random.uniform(0.5, 2.0), 3),
                "nh3": round(random.uniform(0.1, 1.0), 3),
                "lux": round(random.uniform(100, 600), 1)
            })

    return jsonify(rows)

@app.route("/status")
def status():
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM status")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template_string("<h1>Status Table</h1>" + str(results))

@app.route("/targets")
def get_targets():

    """Expose latest detections as JSON."""
    # ???
    detections = target_system.get_detections()
    print("Targets:", detections)

    data = target_system.get_gauge_pressure()

    dets = [
        str({
            "type": str(det.type.value),
            "confidence": float(det.confidence),
            "x": float(det.x),
            "y": float(det.y),
            "width": float(det.width),
            "height": float(det.height),
            "angle": det.angle if det.angle is not None else "None",
            "location": det.location if det.location is not None else "None",
            "id": int(det.id) if det.id is not None else "None"
            })
        for det in detections
    ]

    return jsonify({ "detections": dets, "data": data })
    # return jsonify({})

if __name__ == '__main__':
    init_db()
    print("Database initialized at", DB_PATH)
    app.run(host='0.0.0.0', port=8080, debug=False)
