from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
import numpy as np
import cv2
import math
import time
import threading

class DetectionType(Enum):
    AruCo = "AruCo"
    Valve = "Valve"
    Gauge = "Gauge"

@dataclass 
class Detection:
    type: DetectionType
    confidence: float
    x: int
    y: int
    width: int
    height: int
    angle: Optional[float] # Angle in degrees, only for Gauge type detections


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
        self._latest_image: Optional[bytes] = None
        self._thr: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def get_image_bytes(self) -> bytes: #cv2.imencode output
        with self._lock:
            return self._latest_image
    
    def get_detections(self) -> list[Detection]:
        with self._lock:
            return self._latest_detections

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
                frame, detections = self.execute()
            except Exception as e:
                #Keep loop alive on error
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

    def _encode_np_bgr_to_mjpeg(self, np_bgr: np.ndarray) -> bytes:
        (flag, encoded_image) = cv2.imencode(".jpg", np_bgr)
        if flag:
            return (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encoded_image) + b'\r\n')
        raise RuntimeError("Failed to encode image")

    def make_image(self) -> np.ndarray:
        np_image = np.ones((480, 640, 3), dtype=np.uint8) * 255
        np_hsv_image = cv2.cvtColor(np_image, cv2.COLOR_BGR2HSV)
        np_hsv_image[..., 1] = 255  # Full saturation
        np_hsv_image[..., 0] = (int(time.monotonic()) % 60) * 3  # Change hue over time
        np_image = cv2.cvtColor(np_hsv_image, cv2.COLOR_HSV2BGR)
        return np_image

    def make_detections(self) -> list[Detection]:
        mock_detection = Detection(
            type=DetectionType.Gauge,
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
        encoded_image = self._encode_np_bgr_to_mjpeg(image)
        return encoded_image, detections

    
if __name__ == "__main__":
    def on_new_image():
        print("callback: new image ready")

    dummy = TargetDetectionDummy(cb=on_new_image)
    dummy.start()
    try:
        for _ in range(3):
            if dummy.wait_for_new_image(timeout=2.0):
                print("waiter saw a frame; dets:", dummy.get_detections())
            else:
                print("timeout waiting for frame")
    finally:
        dummy.stop()