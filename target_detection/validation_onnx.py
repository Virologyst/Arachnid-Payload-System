import cv2
import numpy as np
from pathlib import Path

# Try modern OpenVINO; fallback to legacy IE if that's what you have installed
ov_core = None
try:
    from openvino.runtime import Core
    ov_core = Core()
    use_ov_runtime = True
except Exception:
    from openvino.inference_engine import IECore  # legacy
    ov_core = IECore()
    use_ov_runtime = False

import torch
from torchvision.ops import nms

MODEL_XML = 'yolov5/yolov5s_sku.xml'
MODEL_BIN = 'yolov5/yolov5s_sku.bin'
IMG_PATH = 'yolov5/dataset/test/images/6f2f8e97-2b78-428c-9121-e47e748f7341_png.rf.775b13bc12a113eeec19b26c22744807.jpg'
IMG_SIZE = 416
CONF_THRES = 0.25
IOU_THRES = 0.45
N_CLASSES = 6  # adjust to your model

# --- utils ---
def letterbox(im, new_size=416, color=(114,114,114)):
    h, w = im.shape[:2]
    scale = min(new_size / h, new_size / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    im_resized = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_LINEAR)
    top = (new_size - nh) // 2
    bottom = new_size - nh - top
    left = (new_size - nw) // 2
    right = new_size - nw - left
    im_padded = cv2.copyMakeBorder(im_resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im_padded, scale, left, top

def xywh_to_xyxy(xywh):
    # xywh in pixels (center-x, center-y, width, height)
    x, y, w, h = xywh.T
    x1 = x - w/2
    y1 = y - h/2
    x2 = x + w/2
    y2 = y + h/2
    return np.stack([x1, y1, x2, y2], axis=1)

def draw_boxes(frame, boxes, scores, cls_ids):
    for (x1,y1,x2,y2), sc, c in zip(boxes, scores, cls_ids):
        p1 = (int(x1), int(y1)); p2 = (int(x2), int(y2))
        cv2.rectangle(frame, p1, p2, (0,128,0), 2)
        label = f"{int(c)}:{sc:.2f}"
        cv2.putText(frame, label, (p1[0], max(0, p1[1]-5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,128,0), 1, cv2.LINE_AA)
    return frame

# --- load model ---
if use_ov_runtime:
    model = ov_core.read_model(MODEL_XML)
    compiled = ov_core.compile_model(model, "CPU")
    input_port = compiled.input(0)
    output_port = compiled.output(0)
else:
    net = ov_core.read_network(model=MODEL_XML, weights=MODEL_BIN)
    input_blob = next(iter(net.input_info))
    compiled = ov_core.load_network(network=net, device_name="CPU")

# --- read & preprocess image (letterbox like YOLO) ---
orig = cv2.imread(IMG_PATH, cv2.IMREAD_COLOR)
assert orig is not None, f"Could not read image at {IMG_PATH}"
lb, scale, padL, padT = letterbox(orig, IMG_SIZE)
# BGR->RGB, NCHW, float32, [0,1]
inp = lb[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
inp = np.expand_dims(inp, 0)

# --- inference ---
if use_ov_runtime:
    res = compiled([inp])
    out = res[output_port]  # usually [1, N, 5+nc] with xywh
else:
    res = compiled.infer(inputs={input_blob: inp})
    # try common keys
    out = None
    for k in ("output", "output0", "StatefulPartitionedCall/output_0", next(iter(res))):
        if k in res:
            out = res[k]
            break
    assert out is not None, f"Couldn't find output tensor in keys: {list(res.keys())}"

# --- postprocess ---
# Expect shape [1, N, 5+nc] with xywh in pixels (already at 416 space) or normalized.
pred = np.squeeze(out, axis=0)

# If values look normalized (<=1.5), assume they’re normalized to input size and scale to pixels
if np.quantile(pred[:, :4], 0.95) <= 1.5:
    pred[:, 0] *= IMG_SIZE
    pred[:, 1] *= IMG_SIZE
    pred[:, 2] *= IMG_SIZE
    pred[:, 3] *= IMG_SIZE

xyxy = xywh_to_xyxy(pred[:, :4])

obj = pred[:, 4:5]                       # [N,1]
cls_probs = pred[:, 5:5+N_CLASSES]       # [N,C]
# if model exported with all classes but your N_CLASSES is smaller/larger, clamp safely
cls_probs = cls_probs[:, :N_CLASSES] if cls_probs.shape[1] >= N_CLASSES else cls_probs

cls_ids = np.argmax(cls_probs, axis=1)
cls_scores = cls_probs[np.arange(cls_probs.shape[0]), cls_ids]
scores = (obj[:, 0] * cls_scores)

# filter by confidence
keep_conf = scores >= CONF_THRES
xyxy = xyxy[keep_conf]
scores = scores[keep_conf]
cls_ids = cls_ids[keep_conf]

# NMS
if len(xyxy):
    # torchvision expects torch tensors
    t_boxes = torch.from_numpy(xyxy).float()
    t_scores = torch.from_numpy(scores).float()
    keep = nms(t_boxes, t_scores, IOU_THRES).numpy()
    xyxy = xyxy[keep]
    scores = scores[keep]
    cls_ids = cls_ids[keep]

# --- map boxes from 416 letterbox back to original image coords ---
# Undo pad + scale
if len(xyxy):
    xyxy[:, [0,2]] -= padL
    xyxy[:, [1,3]] -= padT
    xyxy /= scale
    # clip to image bounds
    h, w = orig.shape[:2]
    xyxy[:, [0,2]] = np.clip(xyxy[:, [0,2]], 0, w - 1)
    xyxy[:, [1,3]] = np.clip(xyxy[:, [1,3]], 0, h - 1)

vis = orig.copy()
if len(xyxy):
    vis = draw_boxes(vis, xyxy, scores, cls_ids)
else:
    cv2.putText(vis, "No detections", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2, cv2.LINE_AA)

# --- show result correctly ---
cv2.namedWindow("detections", cv2.WINDOW_NORMAL)
cv2.imshow("detections", vis)
cv2.waitKey(0)
cv2.destroyAllWindows()