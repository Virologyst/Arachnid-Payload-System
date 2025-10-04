from pathlib import Path
from typing import Callable, Optional
import depthai as dai
import numpy as np
import cv2, time

from .interface import TargetDetectionInterface, Detection

# =========================
# Config
# =========================
INPUT_W = 416
INPUT_H = 416
NUM_CLASSES = 6
LABELS = ['AruCo', 'fire_extinguisher', 'needle_centre', 'needle_tip', 'valve_closed', 'valve_open']  # edit to your names

CONF_THRESH = 0.90          # Ultralytics default-ish for runtime
IOU_THRESH  = 0.65          # Ultralytics default NMS IoU
AGNOSTIC_NMS = False        # Ultralytics default = class-aware
MAX_DET      = 300          # Ultralytics max_det
TOPK_PER_CLASS = 4        # generous; prune by MAX_DET later

SHAVES = 6
CAM_FPS = 30.0

# =========================
# Colors / UI helpers
# =========================
_PALETTE = np.array([
    [56,56,255], [60,179,113], [255,99,71],
    [238,130,238], [255,215,0], [0,165,255]
], dtype=np.uint8)

def _color(cid: int):
    return _PALETTE[cid % len(_PALETTE)].tolist()

def draw_detections(frame: np.ndarray, dets: list[tuple], labels=LABELS) -> np.ndarray:
    """
    dets: list of (cls_id, conf, x1, y1, x2, y2) in pixel coords (ints)
    frame: BGR HxWx3 (draws in-place)
    """
    H, W = frame.shape[:2]
    for cid, conf, x1, y1, x2, y2 in dets:
        cid = int(cid)
        x1 = max(0, min(W-1, int(x1)))
        y1 = max(0, min(H-1, int(y1)))
        x2 = max(0, min(W-1, int(x2)))
        y2 = max(0, min(H-1, int(y2)))
        if x2 <= x1 or y2 <= y1: 
            continue

        color = _color(cid)
        # Box thickness proportional to box perimeter (readable small/large)
        perim = (x2-x1) + (y2-y1)
        th = max(2, min(6, perim // 150))
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, th, cv2.LINE_AA)

        name = labels[cid] if 0 <= cid < len(labels) else f"cls{cid}"
        text = f"{name} {conf:.2f}"
        (tw, th_text), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        bx = x1; by = max(0, y1 - th_text - 6)
        cv2.rectangle(frame, (bx, by), (bx + tw + 6, by + th_text + 6), color, -1)
        cv2.putText(frame, text, (bx + 3, by + th_text + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv2.LINE_AA)
    return frame

# =========================
# Ultralytics-like decoder
# =========================
def _sigmoid_if_needed(x: np.ndarray) -> np.ndarray:
    # Apply sigmoid only if values look like logits
    if np.nanmax(x) > 1.1 or np.nanmin(x) < -0.1:
        print(f"sigmoid: applying to range {np.nanmin(x):.3f}..{np.nanmax(x):.3f}")
        x = 1.0 / (1.0 + np.exp(-x))
    return x

def _xywh_to_xyxy(xywh: np.ndarray, w=INPUT_W, h=INPUT_H) -> np.ndarray:
    # If coords look normalized, scale to pixels
    if np.max(xywh[:, :4]) <= 1.5:
        xywh = xywh.copy()
        xywh[:, [0,2]] *= w
        xywh[:, [1,3]] *= h
    cx, cy, bw, bh = xywh[:,0], xywh[:,1], xywh[:,2], xywh[:,3]
    x1 = np.clip(cx - bw/2, 0, w)
    y1 = np.clip(cy - bh/2, 0, h)
    x2 = np.clip(cx + bw/2, 0, w)
    y2 = np.clip(cy + bh/2, 0, h)
    return np.stack([x1,y1,x2,y2], axis=1)

def _bbox_iou_xyxy(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # a: [M,4], b: [N,4]
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(br - tl, 0, None)
    inter = wh[:, :, 0] * wh[:, :, 1]
    area_a = (a[:,2]-a[:,0]) * (a[:,3]-a[:,1])
    area_b = (b[:,2]-b[:,0]) * (b[:,3]-b[:,1])
    return inter / (area_a[:,None] + area_b[None,:] - inter + 1e-9)

def _filter_dets_by_loc(boxes: np.ndarray, scores: np.ndarray, classes: np.ndarray,
                       band_px: int = 16, h: int = INPUT_H):
    y2 = boxes[:, 3]
    if float(np.nanmax(np.abs(y2))) <= 1.01:   # looks normalized
        print("filter: assuming normalized coords")
        y2_px = y2 * h
    else:
        y2_px = y2
    drop = y2_px >= (h - band_px)
    return boxes[~drop], scores[~drop], classes[~drop]

def _nms_ultralytics(boxes: np.ndarray, scores: np.ndarray, classes: np.ndarray,
                     iou_thr=IOU_THRESH, max_det=MAX_DET, class_agnostic=AGNOSTIC_NMS) -> np.ndarray:
    """
    Ultralytics-style NMS:
    - sort by conf desc
    - suppress boxes IoU>thr
    - class-aware by default (agnostic=False)
    """
    if boxes.size == 0:
        return np.empty((0,), dtype=np.int32)
    
    boxes, scores, classes = _filter_dets_by_loc(boxes, scores, classes)
    if boxes.size == 0:
        print("empty")
        return np.empty((0,), dtype=np.int32)

    order = np.argsort(-scores)
    boxes = boxes[order]
    scores = scores[order]
    classes = classes[order]

    keep_global = []
    if class_agnostic:
        idx = np.arange(len(scores))
        while idx.size:
            i = idx[0]
            keep_global.append(order[i])
            if len(keep_global) >= max_det or idx.size == 1:
                break
            ious = _bbox_iou_xyxy(boxes[:1], boxes[1:])[0]
            remain = np.where(ious <= iou_thr)[0] + 1
            boxes, scores, classes = boxes[remain], scores[remain], classes[remain]
            order = order[remain]
            idx = np.arange(len(scores))
    else:
        # class-aware: process per class, then cap global
        kept_all = []
        for c in np.unique(classes):
            idx = np.where(classes == c)[0]
            b = boxes[idx]
            s = scores[idx]
            ord_c = np.argsort(-s)
            b = b[ord_c]; s = s[ord_c]
            sel = []
            while len(b):
                sel.append(idx[ord_c[0]])
                if len(sel) >= TOPK_PER_CLASS or len(b) == 1:
                    break
                ious = _bbox_iou_xyxy(b[:1], b[1:])[0]
                keep = np.where(ious <= iou_thr)[0] + 1
                b = b[keep]; s = s[keep]
                ord_c = ord_c[keep]
            kept_all.extend(sel)
        # Respect global cap by confidence
        kept_all = np.array(kept_all, dtype=np.int32)
        # kept_all are indices in 'order' space; map to original
        confs = scores[np.isin(order, kept_all, assume_unique=False)]
        # build (orig_idx, conf) list
        orig_conf = [(idx, scores[np.where(order == idx)[0][0]]) for idx in kept_all]
        orig_conf.sort(key=lambda t: -t[1])
        keep_global = [t[0] for t in orig_conf[:max_det]]

    return np.array(keep_global, dtype=np.int32)

def decode_yolov5_ultra(pkt: dai.NNData) -> list[tuple]:
    """
    Decodes Ultralytics-style YOLO output into:
    [(cls_id, conf, x1, y1, x2, y2), ...] in 416x416 input pixels.
    """
    # Try common layer names; else pick largest
    names = pkt.getAllLayerNames()
    name = "output0" if "output0" in names else (max(names, key=lambda n: len(pkt.getLayerFp16(n))) if names else None)
    if not name:
        return []

    raw = np.array(pkt.getTensor(name), dtype=np.float32, copy=False) \
        if hasattr(pkt, "getTensor") else np.array(pkt.getLayerFp16(name), dtype=np.float32)
    if raw.size == 0:
        return []

    # Infer columns when possible
    cols_expected = 5 + NUM_CLASSES
    if raw.size % cols_expected != 0:
        # fall back to trusting caller: reshape with whatever divides evenly ≥ 6
        for c in range(5 + NUM_CLASSES, 5, -1):
            if raw.size % c == 0:
                cols_expected = c
                break
    preds = raw.reshape(-1, cols_expected)

    xywh = preds[:, :4]
    obj  = _sigmoid_if_needed(preds[:, 4])
    cls  = _sigmoid_if_needed(preds[:, 5:]) if preds.shape[1] > 5 else np.zeros((preds.shape[0],1), np.float32)

    if cls.size:
        cls_id = np.argmax(cls, axis=1)
        cls_conf = cls[np.arange(cls.shape[0]), cls_id]
        conf = obj * cls_conf
    else:
        cls_id = np.zeros((preds.shape[0],), dtype=np.int64)
        conf = obj

    # Early threshold (Ultralytics does this before NMS)
    m = conf >= CONF_THRESH
    if not np.any(m):
        return []

    xyxy = _xywh_to_xyxy(xywh[m])
    conf = conf[m]
    cls_id = cls_id[m]

    # NMS
    keep = _nms_ultralytics(xyxy, conf, cls_id, iou_thr=IOU_THRESH, max_det=MAX_DET, class_agnostic=AGNOSTIC_NMS)
    if keep.size == 0:
        return []
    # keep are indices in the filtered set’s original order,
    # but we want them sorted by conf desc like Ultralytics:
    order = np.argsort(-conf)
    # map keep to that order
    order_keep_mask = np.isin(order, keep)
    final_idx = order[order_keep_mask]

    dets = []
    for i in final_idx:
        x1,y1,x2,y2 = xyxy[i]
        dets.append((int(cls_id[i]), float(conf[i]), int(x1), int(y1), int(x2), int(y2)))
    return dets

class TargetDetection(TargetDetectionInterface):
    def __init__(self, cb:Optional[Callable]=None, frames_by_seq: dict[int, dai.ImgFrame] = {}, 
                 nn_by_seq: dict[int, dai.NNData] = {}, MAX_BUF = 16):
        super().__init__(cb)
        superblob_path = Path(__file__).parent / "model.rvc2.tar.xz"
        assert superblob_path.exists(), f"Superblob path {superblob_path} does not exist!"

        archive = dai.NNArchive(superblob_path)
        superblob = archive.getSuperBlob()
        if superblob is None:
            raise RuntimeError(f"Failed to load superblob from {superblob_path}")
        blob = superblob.getBlobWithNumShaves(SHAVES)

        p = dai.Pipeline()

        # Camera → 416×416 (CROP) → NN
        cam = p.create(dai.node.Camera).build()
        img = cam.requestOutput((INPUT_W, INPUT_H),
                                dai.ImgFrame.Type.BGR888p,
                                resizeMode=dai.ImgResizeMode.CROP,
                                fps=CAM_FPS)

        nn = p.create(dai.node.NeuralNetwork)
        nn.setBlob(blob)
        nn.setNumInferenceThreads(2)
        img.link(nn.input)

        # Queues (small, non-blocking)
        x_img = nn.passthrough.createOutputQueue(maxSize=4, blocking=False)
        x_nn  = nn.out.createOutputQueue(maxSize=4, blocking=False)
        self.pipeline = p
        self.x_img = x_img
        self.x_nn = x_nn
        self.frames_by_seq = frames_by_seq
        self.nn_by_seq = nn_by_seq
        self.MAX_BUF = MAX_BUF
        p.start()

    def _get_seq(self, pkt):
        try:
            return pkt.getSequenceNum()
        except AttributeError:
            # fallback if needed
            return int(pkt.getTimestampDevice().total_seconds() * 1000)

    def _pop_ready_pairs(self):
        ready = []
        common = set(self.frames_by_seq.keys()) & set(self.nn_by_seq.keys())
        for seq in sorted(common):
            ready.append((self.frames_by_seq.pop(seq), self.nn_by_seq.pop(seq)))
        # trim runaway buffers
        for buf in (self.frames_by_seq, self.nn_by_seq):
            if len(buf) > self.MAX_BUF:
                for k in sorted(buf.keys())[:-self.MAX_BUF]:
                    buf.pop(k, None)
        return ready

    def _encode_np_bgr_to_mjpeg(self, np_bgr: np.ndarray) -> bytes:
        (flag, encoded_image) = cv2.imencode(".jpg", np_bgr)
        if flag:
            return (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encoded_image) + b'\r\n')
        raise RuntimeError("Failed to encode image")

    def execute(self) -> tuple[bytes, list[Detection]]:
        while self.x_img.has():
            f = self.x_img.get()
            self.frames_by_seq[self._get_seq(f)] = f
        while self.x_nn.has():
            n = self.x_nn.get()
            self.nn_by_seq[self._get_seq(n)] = n

        for f, out in self._pop_ready_pairs():
            frame = f.getCvFrame()          # exact 416×416 used for inference
            dets = decode_yolov5_ultra(out)
            if dets:
                draw_detections(frame, dets, LABELS)

        return frame, dets