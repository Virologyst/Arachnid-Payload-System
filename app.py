import subprocess
from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    jsonify,
    send_from_directory,
    render_template_string)
import mysql.connector
import sqlite3
import subprocess
import threading
import os

# app = Flask(__name__)
app = Flask(__name__, static_folder="static", static_url_path="")
DB_PATH = 'database/egh455.db'

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'raspi123',
    'database': 'pi_data'
}

def do_update():
    # Pull latest code from GitHub
    subprocess.run(["/usr/bin/git", "pull"], cwd="/home/egh455/EGH455")
    # Restart the systemd service to load new code
    subprocess.run(["/usr/bin/sudo", "systemctl", "restart", "egh455.service"])

# @app.route('/')
# def home():
#     return render_template('dashboard.html')

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static_files(path):
    return send_from_directory(app.static_folder, path)

# --- Update Route ---
# @app.route("/update", methods=["POST"])
# def update():
#     try:
#         repo_dir = "/home/egh455-g5/EGH455"
#         svelte_dir = os.path.join(repo_dir, "interface")
#         static_dir = os.path.join(repo_dir, "static")
#
#         # 1️⃣ Pull latest code
#         subprocess.run(["git", "pull"], cwd=repo_dir, check=True)
#
#         # 2️⃣ Install Svelte deps (if new packages were added)
#         subprocess.run(["npm", "install"], cwd=svelte_dir, check=True)
#
#         # 3️⃣ Build Svelte
#         subprocess.run(["npm", "run", "build"], cwd=svelte_dir, check=True)
#
#         # 4️⃣ Copy build to Flask static folder
#         subprocess.run(["cp", "-r", "build/.", static_dir], cwd=svelte_dir, check=True)
#
#         # 5️⃣ Restart the service
#         subprocess.run(["sudo", "systemctl", "restart", "egh455.service"], check=True)
#
#         return jsonify({"status": "ok", "message": "Update complete"})
#     except subprocess.CalledProcessError as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/update", methods=["POST"])
def update():
    try:
        # Run the deploy script
        subprocess.run(["deploy"], check=True)
        return jsonify({"status": "ok", "message": "Deployment triggered"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/status')
def status():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM status")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('status.html', status_data=results)

# @app.route("/update", methods=["POST"])
# def update():
#     # spawn the update in a new thread so Flask can return immediately
#     threading.Thread(target=do_update).start()
#     return jsonify({"status": "ok"})
#
# @app.route("/restart", methods=["POST"])
# def restart():
#     # Restart the systemd service manually
#     subprocess.run(["/usr/bin/sudo", "systemctl", "restart", "egh455.service"])
#     return redirect(url_for("dashboard"))

# Fake data for dashboard

@app.route("/panel/<view>")
def panel_content(view):
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
