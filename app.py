from flask import Flask, render_template
import mysql.connector

app = Flask(__name__)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'raspi123',  # swap out, obviously
    'database': 'pi_data'
}

@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/status')
def status():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM status")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('status.html', status_data=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
