#!/usr/bin/env python3
"""Run an extracted Flock TFLite detector on images (model, NOT capture data).

Tests the model's behavior on YOUR supplied images — synthetic or public — never on
captured surveillance frames. Reports detections per class with confidence.

Setup (Python 3.11; tflite_runtime has no 3.12 wheel):
    python3.11 -m venv venv && venv/bin/pip install 'numpy<2' pillow tflite-runtime

Usage:
    venv/bin/python detect.py --model MLM-2854-pico3-best-fp16.tflite \
        --labels label_map_all_vehicle.json --input ./test_images --conf 0.35
"""
import argparse, glob, json, os
import numpy as np
from PIL import Image
import tflite_runtime.interpreter as tfl

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--labels", help="label_map json with a 'labels' list of {id,name} objects; else generic class indices")
ap.add_argument("--input", required=True, help="image file or directory")
ap.add_argument("--conf", type=float, default=0.35)
a = ap.parse_args()

labels = None
if a.labels and os.path.exists(a.labels):
    j = json.load(open(a.labels))
    labels = [l["name"] for l in sorted(j.get("labels", []), key=lambda x: x.get("id", 0))]

it = tfl.Interpreter(model_path=a.model); it.allocate_tensors()
ind, outd = it.get_input_details()[0], it.get_output_details()[0]
H, W = ind["shape"][1], ind["shape"][2]
print(f"model input={list(ind['shape'])} output={list(outd['shape'])}")

def letterbox(im):
    im = im.convert("RGB"); w, h = im.size; s = min(W/w, H/h); nw, nh = int(w*s), int(h*s)
    c = Image.new("RGB", (W, H), (114, 114, 114)); c.paste(im.resize((nw, nh)), ((W-nw)//2, (H-nh)//2))
    return c
sig = lambda x: 1/(1+np.exp(-x))
files = [a.input] if os.path.isfile(a.input) else sorted(glob.glob(os.path.join(a.input, "*")))
for p in files:
    try: im = Image.open(p)
    except Exception: continue
    arr = np.asarray(letterbox(im)).astype(np.float32)/255.0
    it.set_tensor(ind["index"], arr[None, ...]); it.invoke()
    out = it.get_tensor(outd["index"])[0]
    if out.shape[0] < out.shape[-1]: out = out.T  # (ch,N) -> (N,ch)
    nc = out.shape[1] - 5
    obj, cls = out[:, 4], out[:, 5:5+nc]
    if obj.max() > 1 or cls.max() > 1: obj, cls = sig(obj), sig(cls)
    conf = obj*cls.max(axis=1); cid = cls.argmax(axis=1); keep = conf >= a.conf
    print(f"\n{os.path.basename(p)}: {int(keep.sum())} dets >= {a.conf}")
    for c in range(nc):
        m = keep & (cid == c)
        if m.any():
            nm = labels[c] if labels and c < len(labels) else f"class{c}"
            print(f"   {nm:14} count={int(m.sum()):4} maxconf={conf[m].max():.2f}")
