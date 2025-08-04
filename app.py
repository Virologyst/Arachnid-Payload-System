

# ───── Standard Library ─────
import os
import time
import datetime
from collections import deque
import logging

# ───── Third-Party ─────
import cv2
import depthai as dai
import smbus2
from flask import (
    Flask, Response, jsonify,
    send_from_directory, render_template_string,
    send_file
)

# --- Enviro+ sensors ---
from enviroplus import gas
from bme280 import BME280
from ltr559 import LTR559

# ───── App Setup ─────
app = Flask(__name__, static_folder="static", static_url_path="")
DB_PATH = 'database/egh455.db'
IMAGE_DIR = "/home/egh455-g5/DCIM"

# ───── Logging Setup ─────
LOG_BUFFER = deque(maxlen=1000)

class FrontendBufferHandler(logging.Handler):
    def emit(self, record):
        LOG_BUFFER.append(self.format(record))

handler = FrontendBufferHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)

app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)


# ──────────────── FLASK APP ────────────────
# app = Flask(__name__, static_folder="static", static_url_path="")
# DB_PATH = 'database/egh455.db'
# IMAGE_DIR = "/home/egh455-g5/DCIM"


# ──────────────── DATABASE SETUP ────────────────

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'raspi123',
    'database': 'pi_data'
}

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
        # ✅ Correct Pimoroni calls
        temperature = round(bme280_sensor.get_temperature(), 1)
        pressure = round(bme280_sensor.get_pressure(), 1)
        humidity = round(bme280_sensor.get_humidity(), 1)

        gas_readings = gas.read_all()
        oxidising = round(gas_readings.oxidising / 1000, 3)   # kΩ
        reducing = round(gas_readings.reducing / 1000, 3)
        nh3 = round(gas_readings.nh3 / 1000, 3)

        lux = ltr559.get_lux()
        prox = ltr559.get_proximity()

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
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT timestamp, temperature, humidity, pressure, oxidising, reducing, nh3, lux FROM enviro_data ORDER BY timestamp DESC LIMIT 50")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)

@app.route("/status")
def status():
    """Show database status table."""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM status")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template_string("<h1>Status Table</h1>" + str(results))



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
