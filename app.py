import subprocess
from flask import Flask, render_template, redirect, url_for, jsonify
import mysql.connector
import sqlite3

app = Flask(__name__)
DB_PATH = 'database/egh455.db'

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'raspi123',
    'database': 'pi_data'
}

@app.route('/')

def home():
    return render_template('dashboard.html')

# def dashboard():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
#
#     cursor.execute("""
#         SELECT target, co2_ppm, temperature_c, humidity_percent
#         FROM sensor_data
#         ORDER BY target
#     """)
#     sensor_rows = cursor.fetchall()
#
#     conn.close()
#
#     return render_template("dashboard.html", sensors=sensor_rows)

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
#     # Pull latest code from GitHub
#     subprocess.run(["/usr/bin/git", "pull"], cwd="/home/egh455/EGH455")
#     # Restart the systemd service to load new code
#     subprocess.run(["/usr/bin/sudo", "systemctl", "restart", "egh455.service"])
#     return redirect(url_for("dashboard"))

@app.route("/update", methods=["POST"])
def update():
    # Pull latest code from GitHub
    subprocess.run(["/usr/bin/git", "pull"], cwd="/home/egh455/EGH455")
    # Restart the systemd service to load new code
    subprocess.run(["/usr/bin/sudo", "systemctl", "restart", "egh455.service"])
    return jsonify({"status": "ok"})


@app.route("/restart", methods=["POST"])
def restart():
    # Restart the systemd service manually
    subprocess.run(["/usr/bin/sudo", "systemctl", "restart", "egh455.service"])
    return redirect(url_for("dashboard"))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
