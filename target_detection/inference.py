from pathlib import Path
from typing import Callable, Optional
import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsBridge
import numpy as np
import cv2, time, math
from collections import deque

from interface import TargetDetectionInterface, Detection, DetectionType

# =========================
# Config
# =========================
INPUT_W = 512
INPUT_H = 384
NUM_CLASSES = 6

CONF_THRESH = 0.3





class TargetDetection(TargetDetectionInterface):
    def __init__(self, cb:Optional[Callable]=None, frames_by_seq: dict[int, dai.ImgFrame] = {}, 
                 nn_by_seq: dict[int, dai.NNData] = {}, MAX_BUF = 16):
        super().__init__(cb)
        superblob_path = Path(__file__).parent / "model.rvc2.tar.xz"
        assert superblob_path.exists(), f"Superblob path {superblob_path} does not exist!"

        device = dai.Device()
        platform = device.getPlatform()
        img_frame_type = dai.ImgFrame.Type.BGR888p if platform.name != "RVC4" else dai.ImgFrame.Type.BGR888i
        
        pipeline = dai.Pipeline()
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput((INPUT_H, INPUT_W), type=img_frame_type, fps=30)
        nn_archive = dai.NNArchive(str(superblob_path))
        nn_with_parser = pipeline.create(ParsingNeuralNetwork).build(
            cam_out,
            nn_archive
        )

        self.label_encoding = {k: v for k, v in enumerate(nn_archive.getConfig().model.heads[0].metadata.classes)}
        bridge = pipeline.create(ImgDetectionsBridge).build(nn_with_parser.out)
        bridge.setLabelEncoding(self.label_encoding)

        xout_frame = pipeline.create(dai.node.XLinkOut)
        xout_frame.setStreamName("frames")
        cam_out.link(xout_frame.input)

        xout_det = pipeline.create(dai.node.XLinkOut)
        xout_det.setStreamName("detections")
        bridge.out.link(xout_det.input)

        self.q_frame = device.getOutputQueue(name="frames", maxSize=4, blocking=False)
        self.q_det = device.getOutputQueue(name="detections", maxSize=4, blocking=False)

        self.frames = {}
        self.detections = {}
        self.order = deque()
        self.buffer_size = 60

        pipeline.start()
        while not pipeline.isRunning():
            time.sleep(0.01)

    def _pop_synced(self):
        for seq in list(self.order):
            if seq in self.frames and seq in self.detections:
                frame = self.frames.pop(seq)
                dets = self.detections.pop(seq)
                self.order.remove(seq)
                return seq, frame, dets
        return None, None, None

    def _encode_np_bgr_to_mjpeg(self, np_bgr: np.ndarray) -> bytes:
        (flag, encoded_image) = cv2.imencode(".jpg", np_bgr)
        if flag:
            return (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encoded_image) + b'\r\n')
        raise RuntimeError("Failed to encode image")
    
    def _parse_detections(self, dmsg: dai.NNData) -> list[Detection]:
        dets: list[Detection] = []
        for det in dmsg.detections:
            score = getattr(det, 'confidence', None)
            if score is None or score < CONF_THRESH:
                continue
            x1 = int(det.xmin * INPUT_W)
            y1 = int(det.ymin * INPUT_H)
            x2 = int(det.xmax * INPUT_W)
            y2 = int(det.ymax * INPUT_H)
            w = x2 - x1
            h = y2 - y1
            cls = det.label
            name = self.label_encoding.get(cls, str(cls))
            detection = Detection(
                confidence=score if score is not None else 0.0,
                x = x1, y = y1, width = w, height = h,
                type = DetectionType(name),
                angle = None
            )
            dets.append(detection)
        
    def _filter_gauges(self, dets: list[Detection]) -> list[Detection]:
        highest_conf_needle_center = None
        highest_conf_needle_tip = None
        for det in dets:
            if det.type == DetectionType.NeedleCenter:
                if (highest_conf_needle_center is None or 
                    det.confidence > highest_conf_needle_center.confidence):
                    highest_conf_needle_center = det
            elif det.type == DetectionType.NeedleTip:
                if (highest_conf_needle_tip is None or 
                    det.confidence > highest_conf_needle_tip.confidence):
                    highest_conf_needle_tip = det
        filtered = [det for det in dets if det.type not in (DetectionType.NeedleCenter, DetectionType.NeedleTip)]
        
        #Calculate the angle given between them given both are present
        if highest_conf_needle_center is not None and highest_conf_needle_tip is not None:
            center_of_needle_center = (highest_conf_needle_center.x + highest_conf_needle_center.width / 2,
                                        highest_conf_needle_center.y + highest_conf_needle_center.height / 2)
            center_of_needle_tip = (highest_conf_needle_tip.x + highest_conf_needle_tip.width / 2,
                                    highest_conf_needle_tip.y + highest_conf_needle_tip.height / 2)
            
            dy = center_of_needle_tip[1] - center_of_needle_center[1]
            dx = center_of_needle_tip[0] - center_of_needle_center[0]
            theta = math.atan2(dy, dx)
            theta = math.degrees(theta)
            theta = round(theta)
            if theta < 0:
                theta *= -1
                theta = (180 - theta) + 180

            # Sets new starting point
            theta = theta - 90

            # Changes negative theta to appropriate value
            if theta < 0:
                theta *= -1
                theta = theta + 270

            highest_conf_needle_tip.angle = theta
            highest_conf_needle_center.angle = theta
            filtered.append(highest_conf_needle_center)
            filtered.append(highest_conf_needle_tip)
        return filtered


    def execute(self) -> tuple[bytes, list[Detection]] | None:
        fmsg = self.q_frame.tryGet()
        if fmsg is not None:
            seq = fmsg.getSequenceNum()
            self.frames[seq] = fmsg
            self.order.append(seq)

        dmsg = self.q_det.tryGet()
        if dmsg is not None:
            seq = dmsg.getSequenceNum()
            self.detections[seq] = dmsg
            self.order.append(seq)

        seq, fmsg, dmsg = self._pop_synced()
        if fmsg is None:
            while len(self.order) > self.buffer_size:
                old_seq = self.order.popleft()
                self.frames.pop(old_seq, None)
                self.detections.pop(old_seq, None)
            time.sleep(0.01)
        
        frame = fmsg.getCvFrame()
        dets = self._parse_detections(dmsg)
        dets = self._filter_gauges(dets)

        return frame, dets
    
if __name__ == "__main__":
    def on_new_image():
        print("callback: new image ready")

    dummy = TargetDetection(cb=on_new_image)
    dummy.start()
    try:
        for _ in range(300):
            if dummy.wait_for_new_image(timeout=2.0):
                print("waiter saw a frame; dets:", dummy.get_detections())
                image = dummy.get_image_bytes()
                cv2.imshow("Frame", image)
                cv2.waitKey(1)
            else:
                print("timeout waiting for frame")
    finally:
        dummy.stop()

cv2.destroyAllWindows()