# import subprocess
# from flask import (
#     Flask,
#     Resonse,
#     render_template,
#     redirect,
#     url_for,
#     jsonify,
#     send_from_directory,
#     render_template_string)
# import mysql.connector
# import sqlite3
# import subprocess
# import threading
# import os
#
# import cv2
# import depthai as dai
# # from flask import Flask, Response

import os
import cv2
import dai
import subprocess
import mysql.connector
from flask import (
    Flask, Response, jsonify,
    send_from_directory, render_template_string
)

# ──────────────── FLASK APP ────────────────
app = Flask(__name__, static_folder="static", static_url_path="")
DB_PATH = 'database/egh455.db'

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'raspi123',
    'database': 'pi_data'
}
#
# # app = Flask(__name__)
# app = Flask(__name__, static_folder="static", static_url_path="")
# DB_PATH = 'database/egh455.db'
#
# db_config = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': 'raspi123',
#     'database': 'pi_data'
# }

# ──────────────── DEPTHAI CAMERA ────────────────
pipeline = dai.Pipeline()

camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_720_P)
camRgb.setInterleaved(False)

xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
camRgb.video.link(xoutRgb.input)

device = dai.Device(pipeline)
qRgb = device.getOutputQueue(name="rgb", maxSize=30, blocking=False)

def gen_frames():
    """Generate MJPEG frames from DepthAI."""
    while True:
        inRgb = qRgb.get()
        frame = inRgb.getCvFrame()
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ──────────────── ROUTES ────────────────

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

@app.route("/update", methods=["POST"])
def update():
    """Trigger deploy script & restart service."""
    try:
        subprocess.run(["deploy"], check=True)
        return jsonify({"status": "ok", "message": "Deployment triggered"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status")
def status():
    """Show database status table."""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM status")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('status.html', status_data=results)

@app.route("/panel/<view>")
def panel_content(view):
    """Dynamic panel content loader for dashboard tabs."""
    if view == "sensors":
        return render_template_string("""
            <h2>Sensor Data</h2>
            <p>Temperature: 22.3°C</p>
            <p>Humidity: 14%</p>
            <p>CO₂: 380 ppm</p>
        """)
    elif view == "logs":
        return render_template_string("""
            <h2>Logs</h2>
            <p>(System logs will be displayed here)</p>
        """)
    elif view == "targets":
        return render_template_string("""
            <h2>Targets</h2>
            <p>No targets detected yet.</p>
        """)
    elif view == "system":
        return render_template_string("""
            <h2>System Controls</h2>
            <button onclick="fetch('/update', {method:'POST'})">🔄 Update & Restart</button>
        """)
    else:
        return "Invalid panel", 404

# def do_update():
#     # Pull latest code from GitHub
#     subprocess.run(["/usr/bin/git", "pull"], cwd="/home/egh455/EGH455")
#     # Restart the systemd service to load new code
#     subprocess.run(["/usr/bin/sudo", "systemctl", "restart", "egh455.service"])
#
# # @app.route('/')
# # def home():
# #     return render_template('dashboard.html')
#
# @app.route("/")
# def serve_index():
#     return send_from_directory(app.static_folder, "index.html")
#
# @app.route("/<path:path>")
# def serve_static_files(path):
#     return send_from_directory(app.static_folder, path)
#
#
# def gen_frames():
#     # Create DepthAI pipeline
#     pipeline = dai.Pipeline()
#     camRgb = pipeline.create(dai.node.ColorCamera)
#     camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
#     camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_720_P)
#
#     xoutRgb = pipeline.create(dai.node.XLinkOut)
#     xoutRgb.setStreamName("rgb")
#     camRgb.video.link(xoutRgb.input)
#
#     # Start device and output queue
#     with dai.Device(pipeline) as device:
#         qRgb = device.getOutputQueue(name="rgb", maxSize=30, blocking=False)
#
#         while True:
#             inRgb = qRgb.get()
#             frame = inRgb.getCvFrame()
#             ret, buffer = cv2.imencode('.jpg', frame)
#             frame = buffer.tobytes()
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
#
# @app.route('/video_feed')
# def video_feed():
#     return Response(gen_frames(),
#                     mimetype='multipart/x-mixed-replace; boundary=frame')
#
# @app.route("/update", methods=["POST"])
# def update():
#     try:
#         # Run the deploy script
#         subprocess.run(["deploy"], check=True)
#         return jsonify({"status": "ok", "message": "Deployment triggered"})
#     except subprocess.CalledProcessError as e:
#         return jsonify({"status": "error", "message": str(e)}), 500
#
#
# @app.route('/status')
# def status():
#     conn = mysql.connector.connect(**db_config)
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM status")
#     results = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     return render_template('status.html', status_data=results)
#
# # @app.route("/update", methods=["POST"])
# # def update():
# #     # spawn the update in a new thread so Flask can return immediately
# #     threading.Thread(target=do_update).start()
# #     return jsonify({"status": "ok"})
# #
# # @app.route("/restart", methods=["POST"])
# # def restart():
# #     # Restart the systemd service manually
# #     subprocess.run(["/usr/bin/sudo", "systemctl", "restart", "egh455.service"])
# #     return redirect(url_for("dashboard"))
#
# # Fake data for dashboard
#
# @app.route("/panel/<view>")
# def panel_content(view):
#     if view == "sensors":
#         return render_template_string("""
#             <h2>Sensor Data</h2>
#             <p>Temperature: 22.3°C</p>
#             <p>Humidity: 14%</p>
#             <p>CO₂: 380 ppm</p>
#         """)
#     elif view == "logs":
#         return render_template_string("""
#             <h2>Logs</h2>
#             <p>(System logs will be displayed here)</p>
#         """)
#     elif view == "targets":
#         return render_template_string("""
#             <h2>Targets</h2>
#             <p>No targets detected yet.</p>
#         """)
#     elif view == "system":
#         return render_template_string("""
#             <h2>System Controls</h2>
#             <button onclick="fetch('/update', {method:'POST'})">🔄 Update & Restart</button>
#         """)
#     else:
#         return "Invalid panel", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
