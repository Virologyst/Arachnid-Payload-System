# Arachnid Payload System

An autonomous sensing and inspection payload built on a Raspberry Pi. It combines on-device computer vision, environmental monitoring and an actuated drill mechanism, all controlled and monitored through a web dashboard.

## Features

- **Target detection** — a custom-trained detection model runs on a Luxonis OAK camera (DepthAI, RVC2) to identify:
  - valves (open / closed)
  - pressure gauges (needle centre and tip), with the gauge reading converted to a pressure value
  - ArUco markers (5×5 dictionary, detected with OpenCV using calibrated camera intrinsics)
- **Live video** — annotated MJPEG stream from the camera, with still-image capture.
- **Environmental sensing** — Pimoroni Enviro+ readings for temperature (CPU-heat compensated), humidity, pressure, oxidising / reducing / NH₃ gas and light / proximity, logged to SQLite.
- **On-board LCD** — the Enviro+ ST7735 display can show the device IP, live detections or temperature.
- **Automatic drill** — a continuous-rotation servo drives the drill. It runs automatically when the moving-average gauge pressure falls below 2 bar, or on demand through the API.
- **Web dashboard** — a SvelteKit single-page app for live video, sensor charts, detections, captured images and logs.

## Hardware

| Component | Purpose |
|---|---|
| Raspberry Pi | Host for the Flask server and sensor drivers |
| Luxonis OAK camera (RVC2) | On-device neural-network inference and video |
| Pimoroni Enviro+ | BME280, LTR559, gas sensor and ST7735 LCD |
| Continuous-rotation servo on GPIO 13 | Drill actuation |

## Repository layout

```
app.py                  Main Flask server: API, video stream, sensors, LCD and drill threads
enviro.py               Stand-alone Enviro+ sensor / LCD script
drill.py                Stand-alone drill servo test script
camera_stream.py        Early camera streaming prototype (unused)
Drill/                  Drill module notes and code
interface/              SvelteKit web dashboard
target_detection/
  inference.py          DepthAI pipeline and detection parsing
  interface.py          Detection types, ArUco detection, gauge-pressure logic, dummy backend
  model.rvc2.tar.xz     Compiled model archive loaded at runtime
  *_config.yaml         Model training configurations
  YoloV5_training.ipynb Training and export notebook
  yolov5/               Ultralytics YOLOv5 (third-party, AGPL-3.0)
requirements.txt        Python dependencies
```

## Getting started

### 1. Python backend (on the Raspberry Pi)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install depthai depthai-nodes enviroplus pimoroni-bme280 ltr559 st7735 fonts font-roboto
```

Enable I²C and SPI on the Pi (`sudo raspi-config` → Interface Options) so the Enviro+ and LCD can be reached.

### 2. Web dashboard

```bash
cd interface
npm install
npm run build
```

The static build is written to `interface/build/`. Flask serves the dashboard from a `static/` folder next to `app.py`, so copy the build output there:

```bash
rm -rf static && cp -r interface/build static
```

During front-end development you can run `npm run dev` instead.

### 3. Run

```bash
python app.py
```

The server listens on port **8080**. Open `http://<pi-ip>:8080` in a browser. The IP can also be shown on the Enviro+ LCD.

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Web dashboard |
| GET | `/video_feed` | Annotated MJPEG camera stream |
| GET | `/targets` | Latest detections and gauge pressure |
| GET | `/enviro` | Current Enviro+ readings (also logged to the database) |
| GET | `/enviro/history` | Last 10 minutes of sensor readings |
| POST | `/capture` | Save a still image |
| GET | `/images` | List captured images |
| GET | `/images/<filename>` | Fetch a captured image |
| DELETE | `/images/delete/<filename>` | Delete a captured image |
| POST | `/drill` | Run the drill sequence |
| POST | `/lcd/on`, `/lcd/off` | Turn the LCD on or off |
| POST | `/lcd/show/ip` | Show the device IP on the LCD |
| POST | `/lcd/show/liveDetections` | Show live detections on the LCD |
| POST | `/lcd/show/temperature` | Show temperature on the LCD |
| GET, POST | `/logs` | Read or append server logs |
| GET | `/status` | System status table |
| POST | `/update` | Run the deployment script |

## Data storage

Sensor readings and status flags are stored in SQLite at `database/` (created on first run). Captured images are saved to the directory set by `IMAGE_DIR` in `app.py`.

## Model training

The detector was trained on a custom labelled dataset at 512×384 input and compiled for the OAK's RVC2 processor. The training configs are in `target_detection/*_config.yaml`, and the YOLOv5 training and export workflow is in `target_detection/YoloV5_training.ipynb`.

## Third-party code

`target_detection/yolov5/` contains [Ultralytics YOLOv5](https://github.com/ultralytics/yolov5), licensed under AGPL-3.0. See `target_detection/yolov5/LICENSE`.
