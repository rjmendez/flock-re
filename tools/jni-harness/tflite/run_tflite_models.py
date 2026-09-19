#!/usr/bin/env python3
"""
Component A of the flock-alpr JNI/ML harness: emulator-free, network-free
TFLite inference smoke test.

Loads the REAL extracted .tflite model weights from the firmware dump
(re/deep/tflite-models/extracted/assets/flock_models/) and feeds them
PURELY SYNTHETIC, procedurally-generated tensors (noise / gradient / flat
color / hand-drawn primitive shapes). No image from the dump, no real
plate/vehicle photo, is used anywhere in this script.

This process never opens a socket (tflite_runtime's C++ interpreter has
no network code path at all), so there is no phone-home surface to
sinkhole on this leg -- it is offline by construction.

Run:
    /home/rjmendez/flock-alpr/re/mlvenv/bin/python \
        /home/rjmendez/development/flock-re/tools/jni-harness/tflite/run_tflite_models.py
"""
import glob, json, os, sys, time
import numpy as np
from PIL import Image
import tflite_runtime.interpreter as tfl

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = "/home/rjmendez/flock-alpr/re/deep/tflite-models/extracted/assets/flock_models"
INPUT_DIR = os.path.join(os.path.dirname(HERE), "synthetic_inputs")
RESULTS_DIR = os.path.join(os.path.dirname(HERE), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

MODELS = [
    "MLM-2324-nano2-fp16.tflite",
    "MLM-2854-pico3-best-fp16.tflite",
    "yolo_pico3_best-fp16.tflite",
    "flock_small_tf.tflite",
    "MLM-2857-large-fp16.tflite",
]

with open(os.path.join(MODEL_DIR, "label_map_all_vehicle.json")) as f:
    LABEL_MAP = json.load(f)
LABELS = [l["name"] for l in sorted(LABEL_MAP["labels"], key=lambda l: l["id"])]

INPUTS = sorted(glob.glob(os.path.join(INPUT_DIR, "*.jpg")))


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -60, 60)))


def letterbox(im, w, h):
    im = im.convert("RGB")
    iw, ih = im.size
    s = min(w / iw, h / ih)
    nw, nh = max(1, int(iw * s)), max(1, int(ih * s))
    im = im.resize((nw, nh))
    canvas = Image.new("RGB", (w, h), (114, 114, 114))
    canvas.paste(im, ((w - nw) // 2, (h - nh) // 2))
    return canvas


def decode_yolo_style(out, labels, conf_thresh=0.25):
    """Best-effort decode for a YOLO-ish [N, 5+num_classes] or [5+num_classes, N] head."""
    out = np.asarray(out)
    if out.ndim == 3:
        out = out[0]
    if out.shape[0] in (5 + len(labels),) and out.shape[1] != (5 + len(labels)):
        out = out.T
    if out.shape[1] < 5:
        return {"decodable": False, "raw_shape": list(out.shape)}
    obj = out[:, 4]
    ncls = out.shape[1] - 5
    cls = out[:, 5:5 + ncls]
    if obj.max() > 1.0001 or (cls.size and cls.max() > 1.0001) or obj.min() < -0.0001:
        obj = sigmoid(obj)
        cls = sigmoid(cls)
    if cls.size:
        best_cls = cls.argmax(axis=1)
        cls_conf = cls.max(axis=1)
    else:
        best_cls = np.zeros(len(obj), dtype=int)
        cls_conf = np.ones(len(obj))
    conf = obj * cls_conf
    keep = conf >= conf_thresh
    per_label = {}
    for i in range(min(ncls, len(labels))):
        m = keep & (best_cls == i)
        per_label[labels[i]] = {
            "count": int(m.sum()),
            "max_conf": float(conf[m].max()) if m.any() else 0.0,
        }
    return {
        "decodable": True,
        "raw_shape": list(out.shape),
        "num_boxes_total": int(out.shape[0]),
        "num_detections_over_thresh": int(keep.sum()),
        "conf_thresh": conf_thresh,
        "per_label": per_label,
        "global_obj_max": float(obj.max()),
    }


report = {
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "component": "A: emulator-free TFLite interpreter path",
    "models_dir": MODEL_DIR,
    "labels": LABELS,
    "synthetic_inputs": [os.path.basename(p) for p in INPUTS],
    "results": [],
}

print("=== flock-alpr TFLite harness (Component A) ===")
print(f"Labels (from label_map_all_vehicle.json): {LABELS}")
print(f"Synthetic inputs: {[os.path.basename(p) for p in INPUTS]}")
print()

for model_name in MODELS:
    model_path = os.path.join(MODEL_DIR, model_name)
    if not os.path.exists(model_path):
        print(f"[SKIP] {model_name}: not found at {model_path}")
        report["results"].append({"model": model_name, "status": "missing_file"})
        continue

    print(f"--- {model_name} ---")
    t0 = time.time()
    try:
        it = tfl.Interpreter(model_path=model_path)
        it.allocate_tensors()
    except Exception as e:
        print(f"  [FAIL] could not load/allocate: {e!r}")
        report["results"].append({"model": model_name, "status": "load_error", "error": repr(e)})
        continue
    load_s = time.time() - t0

    ind = it.get_input_details()[0]
    outd_list = it.get_output_details()
    shape = ind["shape"]
    H, W = int(shape[1]), int(shape[2])
    dtype = ind["dtype"]
    print(f"  loaded in {load_s:.2f}s  input_shape={list(shape)} dtype={dtype}  "
          f"n_outputs={len(outd_list)} first_output_shape={list(outd_list[0]['shape'])}")

    model_result = {
        "model": model_name,
        "status": "ok",
        "load_time_s": round(load_s, 3),
        "input_shape": [int(x) for x in shape],
        "input_dtype": str(dtype),
        "output_shapes": [[int(x) for x in o["shape"]] for o in outd_list],
        "per_input": [],
    }

    for img_path in INPUTS:
        name = os.path.basename(img_path)
        im = letterbox(Image.open(img_path), W, H)
        arr = np.asarray(im).astype(np.float32) / 255.0
        if dtype == np.uint8:
            arr = (arr * 255).astype(dtype)
        elif dtype == np.int8:
            arr = (arr * 255 - 128).astype(dtype)
        else:
            arr = arr.astype(dtype)
        t1 = time.time()
        it.set_tensor(ind["index"], arr[None, ...])
        it.invoke()
        infer_s = time.time() - t1
        out0 = it.get_tensor(outd_list[0]["index"])[0]
        decoded = decode_yolo_style(out0, LABELS)
        print(f"    [{name}] invoke={infer_s*1000:.1f}ms  {decoded}")
        model_result["per_input"].append({
            "input": name,
            "invoke_time_ms": round(infer_s * 1000, 2),
            "decoded": decoded,
        })
    report["results"].append(model_result)
    print()

out_path = os.path.join(RESULTS_DIR, "tflite_component_a_results.json")
with open(out_path, "w") as f:
    json.dump(report, f, indent=2)
print(f"Full report written to {out_path}")
