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

# ───── Third-Party ─────
import cv2
import depthai as dai

import sqlite3
from flask import (
    Flask, Response, jsonify,
    send_from_directory, render_template_string,
    send_file, request
)

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

# ──────────────── Drilling Mechanism (Nicky ────────────────

# detections = target_system.get_gauge_pressure()
# Note to Nicky - pressure plate detection target_system.get_gauge_pressure() - Lower limit 2 Bar. Needs low pass filter
# Initialise Servo
# servo = AngularServo(12, min_angle=0, max_angle=360, min_pulse_width=0.0005, max_pulse_width=0.0025)

time.sleep(1)

# Initialize Servo (GPIO pin 13)
servo = AngularServo(
    13,
    min_angle=0,
    max_angle=360,
    min_pulse_width=0.0005,
    max_pulse_width=0.0025
)

def Drill():
    print("Starting drill sequence...")
    servo.angle = 360
    time.sleep(93)  # 93 which is almost 1.5 minutes
    servo.angle = 0
    time.sleep(93)
    servo.angle = 90
    print("Drill sequence completed.")


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

# Initialise sensors (Same as examples)
bme280 = BME280()
ltr559 = LTR559()
gas_sensor = gas

try:

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

except Exception as e:
    print("LCD init failed:", e)
    disp = None

# ───── App Setup ─────
app = Flask(__name__, static_folder="static", static_url_path="")

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
            LOG_BUFFER.append(line.strip())

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


# ──────────────── DATABASE SETUP ────────────────
DB_PATH = 'database/egh455.db'
IMAGE_DIR = "/home/egh455-g5/DCIM"

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

# from target_detection.interface import TargetDetectionDummy
# from target_detection.inference import TargetDetection

# # Initialize detection system
# target_system = TargetDetection()

# print("Initialized target system", flush=True)

# target_system.start()

# def gen_frames():
#     """Generate MJPEG frames using the active detection system."""
#     global target_system
#     while True:
#         target_system.wait_for_new_image(timeout=1.0)
#         frame_bytes = target_system.get_image_bytes()
#         if frame_bytes:

#             yield frame_bytes


# # ──────────────── DEPTHAI CAMERA ────────────────

# if not os.path.exists(IMAGE_DIR):
#     os.makedirs(IMAGE_DIR)

# @app.route("/capture", methods=["POST"])
# def capture_image():
#     """Capture a single frame from DepthAI and save it."""
#     try:

#         frame = target_system.get_image_bytes(encode=False)

#         timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"{IMAGE_DIR}/capture_{timestamp}.jpg"

#         cv2.imwrite(filename, frame)
#         return jsonify({"status": "ok", "file": filename})
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# @app.route("/images")
# def list_images():
#     """Return JSON list of saved images (latest 10 first)."""
#     files = sorted(
#         [f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg")],
#         key=lambda x: os.path.getmtime(os.path.join(IMAGE_DIR, x)),
#         reverse=True
#     )
#     latest = files[:10]
#     return jsonify({"images": latest})


# @app.route("/images/<filename>")
# def get_image(filename):
#     """Serve a specific saved image."""
#     return send_file(os.path.join(IMAGE_DIR, filename), mimetype="image/jpeg")


# @app.route("/images/delete/<filename>", methods=["DELETE"])
# def delete_image(filename):
#     """Delete an image from the folder."""
#     try:
#         os.remove(os.path.join(IMAGE_DIR, filename))
#         return jsonify({"status": "ok", "message": f"{filename} deleted"})
#     except FileNotFoundError:
#         return jsonify({"status": "error", "message": "File not found"}), 404

# ──────────────── LCD CONTROL ROUTES (Charlie)  ────────────────

from threading import Thread
mode = 0        # 0 = ip-address, 1 = target-detection, 2 = temperature

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


@app.route("/lcd/show/<mode>", methods=["POST"])
def lcd_show(mode):
    """Show a specific display mode (ip, temperature, humidity, pressure)."""
    global current_mode
    try:
        current_mode = mode
        if mode == 0:
            lcd_show_message(ip)
        elif mode == 1:
            lcd_show_message(f"TEMP: {bme280.get_temperature():.1f}C")
        elif mode == 2:
            lcd_show_message(f"TEMP: {bme280.get_temperature():.1f}C")
        else:
            lcd_show_message(mode.upper())
        return jsonify({"status": "ok", "message": f"LCD showing {mode}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def lcd_loop_thread():
    """Cycle through sensor values automatically."""
    global mode

    # Get the temperature of the CPU for compensation
    def get_cpu_temperature():
        process = Popen(["vcgencmd", "measure_temp"], stdout=PIPE, universal_newlines=True)
        output, _error = process.communicate()
        return float(output[output.index("=") + 1:output.rindex("'")])

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
            proximity = ltr559.get_proximity()

            # If the proximity crosses the threshold, toggle the mode
            if proximity > 1500 and time.time() - last_page > delay:
                mode += 1
                mode %= len(variables)
                last_page = time.time()

            # One mode for each variable
            if mode == 0:
                # variable = "ip-address"
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
                
            if mode == 1:
                # variable = "target-detection"
                print("ADD TARGET DETECTION HERE")

            if mode == 2:
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
Thread(target=lcd_loop_thread, daemon=True).start()

# ──────────────── ROUTES ────────────────

@app.route('/drill', methods=['POST'])
def drill_endpoint():
    try:
        Drill()
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
    try:
        temperature = round(bme280.get_temperature(), 1)
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
    try:
        subprocess.run(["/home/egh455-g5/EGH455/deploy.sh"], check=True)
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
        {
            "type": det.type.value,
            "confidence": det.confidence,
            "x": det.x,
            "y": det.y,
            "width": det.width,
            "height": det.height,
            "angle": det.angle,
        }
        for det in detections
    ]

    return jsonify({ "detections": dets, "data": data })
    # return jsonify({})

if __name__ == '__main__':
    init_db()
    print("Database initialized at", DB_PATH)
    app.run(host='0.0.0.0', port=8080, debug=False)
