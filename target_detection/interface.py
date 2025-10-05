from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
import numpy as np
import cv2
import math
import time
import threading
import traceback

class DetectionType(Enum):
    AruCo = "AruCo"
    ValveOpen = "valve_open"
    ValveClosed = "valve_closed"
    NeedleCenter = "needle_center"
    NeedleTip = "needle_tip"
    FireExtinguisher = "fire_extinguisher"


@dataclass 
class Detection:
    type: DetectionType
    confidence: float
    x: int
    y: int
    width: int
    height: int
    angle: Optional[float] # Angle in degrees, only for Gauge type detections

    def __repr__(self):
        return (f"Detection(type={self.type}, conf={self.confidence:.2f}, "
                f"x={self.x}, y={self.y}, w={self.width}, h={self.height}, "
                f"angle={self.angle})")

# =========================
# Colors / UI helpers
# =========================
_PALETTE = np.array([
    [56,56,255], [60,179,113], [255,99,71],
    [238,130,238], [255,215,0], [0,165,255]
], dtype=np.uint8)

def _color(cid: int):
    return _PALETTE[cid % len(_PALETTE)].tolist()

LABELS = ['AruCo', 'fire_extinguisher', 'needle_center', 'needle_tip', 'valve_closed', 'valve_open'] # Has to be synced with DetectionType enum
def draw_detections(frame: np.ndarray, dets: list[Detection]) -> np.ndarray:
    """
    dets: list of Detection objects
    frame: BGR HxWx3 (draws in-place)
    """
    H, W = frame.shape[:2]
    for det in dets:
        cid = LABELS.index(det.type.value)
        conf = det.confidence
        x1 = max(0, min(W-1, int(det.x)))
        y1 = max(0, min(H-1, int(det.y)))
        x2 = max(0, min(W-1, int(det.x + det.width)))
        y2 = max(0, min(H-1, int(det.y + det.height)))
        if x2 <= x1 or y2 <= y1: 
            continue

        color = _color(cid)
        # Box thickness proportional to box perimeter (readable small/large)
        perim = (x2-x1) + (y2-y1)
        th = max(2, min(6, perim // 150))
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, th, cv2.LINE_AA)

        name = det.type.value
        text = f"{name} {conf:.2f}"
        (tw, th_text), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        bx = x1; by = max(0, y1 - th_text - 6)
        cv2.rectangle(frame, (bx, by), (bx + tw + 6, by + th_text + 6), color, -1)
        cv2.putText(frame, text, (bx + 3, by + th_text + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv2.LINE_AA)
    return frame

class TargetDetectionInterface:
    """
    Base interface with:
      - set_new_image_cb(cb): register a callback
      - start()/stop(): manage background producer
      - get_image_bytes()/get_detections(): thread-safe access to latest
    """
    def __init__(self, cb: Optional[Callable[[], None]] = None):
        self.new_image_cb: Optional[Callable[[], None]] = cb
        self._lock = threading.Lock()
        self._new_image_event = threading.Event()
        self._latest_detections: list[Detection] = []
        self._latest_image: Optional[np.ndarray] = None
        self._thr: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def _encode_np_bgr_to_mjpeg(self, np_bgr: np.ndarray) -> bytes:
        (flag, encoded_image) = cv2.imencode(".jpg", np_bgr)
        if flag:
            return (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encoded_image) + b'\r\n')
        raise RuntimeError("Failed to encode image")

    def get_image_bytes(self, draw_detections_flag: bool = True, encode=True) -> bytes | None:  # cv2.imencode output
        with self._lock:
            if draw_detections_flag and self._latest_detections:
                frame = self._latest_image
                frame = draw_detections(frame, self._latest_detections)
                if encode:
                    return self._encode_np_bgr_to_mjpeg(frame)
                return frame
            if encode:
                return self._encode_np_bgr_to_mjpeg(self._latest_image)
            return self._latest_image
    
    def get_detections(self) -> list[Detection]:
        with self._lock:
            return self._latest_detections

    def get_gauge_pressure(self) -> Optional[float]:
        pressure_map_slope = (5 - 2) / (90 - 0)
        pressure_map_intercept = -1
        with self._lock:
            if self._latest_detections is None:
                return None
            for det in self._latest_detections:
                if det.type == DetectionType.NeedleCenter:
                    angle = det.angle
                    pressure = pressure_map_slope * angle + pressure_map_intercept
                    return pressure  # approximate BAR pressure
        return None

    def set_new_image_cb(self, cb: Optional[callable]):
        self.new_image_cb = cb

    def wait_for_new_image(self, timeout: Optional[float] = None) -> bool:
        wait_result = self._new_image_event.wait(timeout)
        if wait_result:
            self._new_image_event.clear()
        return wait_result
    
    def start(self):
        if self._thr is not None and self._thr.is_alive():
            return
        self._stop.clear()
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()
    
    def stop(self):
        if self._thr is None:
            return
        self._stop.set()
        self._thr.join()
        self._thr = None

    def execute(self) -> tuple[bytes, list[Detection]]:
        raise NotImplementedError("Must be implemented in subclass")

    def _run(self, frequency_hz: float = 60.0):
        period = 1.0 / frequency_hz
        next_t = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            if now < next_t:
                time.sleep(next_t - now)
            next_t = now + period

            try:
                output = self.execute()
                if output is None:
                    continue
                frame, detections = output
            except Exception as e:
                #Keep loop alive on error
                print(traceback.format_exc())
                print(f"Error in TargetDetectionInterface _run: {e}")
                continue

            with self._lock:
                self._latest_image = frame
                self._latest_detections = detections
            
            self._new_image_event.set()
            try:
                if self.new_image_cb is not None:
                    self.new_image_cb()
            except Exception as e:
                print(f"Error in new_image_cb: {e}")
                continue


class TargetDetectionDummy(TargetDetectionInterface):
    def __init__(self, cb:Optional[callable]=None):
        super().__init__(cb)

    def make_image(self) -> np.ndarray:
        np_image = np.ones((480, 640, 3), dtype=np.uint8) * 255
        np_hsv_image = cv2.cvtColor(np_image, cv2.COLOR_BGR2HSV)
        np_hsv_image[..., 1] = 255  # Full saturation
        np_hsv_image[..., 0] = (int(time.monotonic()) % 60) * 3  # Change hue over time
        np_image = cv2.cvtColor(np_hsv_image, cv2.COLOR_HSV2BGR)
        return np_image

    def make_detections(self) -> list[Detection]:
        mock_detection = Detection(
            type=DetectionType.AruCo,
            confidence=0.95,
            x=100,
            y=150,
            width=50,
            height=50,
            angle=math.sin(time.monotonic() / 20.0) # Simulate a changing angle
        )
        return [mock_detection]
    
    def execute(self) -> tuple[bytes, list[Detection]]:
        image = self.make_image()
        detections = self.make_detections()
        return image, detections

    
if __name__ == "__main__":
    def on_new_image():
        print("callback: new image ready")

    dummy = TargetDetectionDummy(cb=on_new_image)
    dummy.start()
    try:
        for _ in range(300000):
            if dummy.wait_for_new_image(timeout=2.0):
                print("waiter saw a frame; dets:", dummy.get_detections())
                
            else:
                print("timeout waiting for frame")
    finally:
        dummy.stop()