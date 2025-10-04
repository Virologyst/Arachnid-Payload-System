# ───── Standard Library ─────
import os
import time
import datetime
from collections import deque
import logging
import subprocess
import random

# ───── Third-Party ─────
import cv2
import depthai as dai
import smbus2
import sqlite3
from flask import (
    Flask, Response, jsonify,
    send_from_directory, render_template_string,
    send_file
)

# --- Enviro+ sensors ---
from enviroplus import gas
from bme280 import BME280
from ltr559 import LTR559

# --- Drill service ---
# Import Libraries needed to run code
from gpiozero import AngularServo
# import curses
# from time import sleep

# Initialise Servo
# servo = AngularServo(12, min_angle=0, max_angle=360, min_pulse_width=0.0005, max_pulse_width=0.0025)

# Initialize Servo (GPIO pin 12)
servo = AngularServo(
    12,
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

# ───── App Setup ─────
app = Flask(__name__, static_folder="static", static_url_path="")


# ───── Logging Setup ─────

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "egh455.log")

LOG_BUFFER = deque(maxlen=1000)

class FrontendBufferHandler(logging.Handler):
    def emit(self, record):
        LOG_BUFFER.append(self.format(record))

# handler = FrontendBufferHandler()
# formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
# handler.setFormatter(formatter)
#
# app.logger.addHandler(handler)
# app.logger.setLevel(logging.INFO)

# Standard formatter
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# File handler (persistent logs)
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)

# Frontend handler (for /logs endpoint)
buffer_handler = FrontendBufferHandler()
buffer_handler.setFormatter(formatter)

# Attach both
app.logger.addHandler(file_handler)
app.logger.addHandler(buffer_handler)
app.logger.setLevel(logging.INFO)



# ──────────────── DATABASE SETUP ────────────────
DB_PATH = 'database/egh455.db'
IMAGE_DIR = "/home/egh455-g5/DCIM"

# db_config = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': 'raspi123',
#     'database': 'pi_data'
# }


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

# ──────────────── DEPTHAI CAMERA ────────────────

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

pipeline = dai.Pipeline()

camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setInterleaved(False)

xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
camRgb.video.link(xoutRgb.input)

@app.route("/capture", methods=["POST"])
def capture_image():
    """Capture a single frame from DepthAI and save it."""
    try:
        if qRgb is None:
            return jsonify({"status": "error", "message": "Camera not initialized"}), 500

        inRgb = qRgb.get()
        frame = inRgb.getCvFrame()

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

def init_depthai():
    for i in range(10):
        try:
            device = dai.Device(pipeline)
            print("Camera initialized.")
            return device, device.getOutputQueue(name="rgb", maxSize=30, blocking=False)
        except RuntimeError as e:
            print(f"DepthAI init failed (attempt {i+1}): {e}")
            time.sleep(5)
    print("Camera failed after retries. Running without camera.")
    return None, None


def gen_frames():
    """Generate MJPEG frames from DepthAI."""
    if qRgb is None:
        while True:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n')
    else:
        while True:
            inRgb = qRgb.get()
            frame = inRgb.getCvFrame()
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ──────────────── Camera and ENVIRO+ SENSOR SETUP ────────────────
bus = smbus2.SMBus(1)
ltr559 = LTR559()
bme280_sensor = BME280(i2c_dev=bus)
device, qRgb = init_depthai()

# ──────────────── ROUTES ────────────────

@app.route('/drill', methods=['POST'])
def drill_endpoint():
    try:
        Drill()
        return jsonify({"status": "success", "message": "Drill activated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/logs")
def get_logs():
    """Return last 50 backend logs."""
    return jsonify(list(LOG_BUFFER))
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
    """Stream DepthAI feed as MJPEG."""
    return Response(gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/enviro')
def get_enviro_data():
    """Read Enviro+ and return JSON."""
    try:
        temperature = round(bme280_sensor.get_temperature(), 1)
        pressure = round(bme280_sensor.get_pressure(), 1)
        humidity = round(bme280_sensor.get_humidity(), 1)

        gas_readings = gas.read_all()
        oxidising = round(gas_readings.oxidising / 1000, 3)   # kΩ
        reducing = round(gas_readings.reducing / 1000, 3)
        nh3 = round(gas_readings.nh3 / 1000, 3)

        lux = ltr559.get_lux()
        prox = ltr559.get_proximity()

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
            "proximity": prox
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
    # return jsonify([d.__dict__ for d in dets])
    return jsonify({})

# def status():
#     """Show database status table."""
#     conn = mysql.connector.connect(**db_config)
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM status")
#     results = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     return render_template_string("<h1>Status Table</h1>" + str(results))


if __name__ == '__main__':
    init_db()
    print("Database initialized at", DB_PATH)
    app.run(host='0.0.0.0', port=8080, debug=False)
