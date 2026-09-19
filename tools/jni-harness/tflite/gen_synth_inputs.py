import numpy as np
from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "synthetic_inputs")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(1337)

noise = rng.integers(0, 256, size=(640, 640, 3), dtype=np.uint8)
Image.fromarray(noise, "RGB").save(f"{OUT}/synth_noise.jpg", quality=95)

solid = np.full((640, 640, 3), 114, dtype=np.uint8)
Image.fromarray(solid, "RGB").save(f"{OUT}/synth_solid_gray.jpg", quality=95)

grad = np.zeros((640, 640, 3), dtype=np.uint8)
xs = np.linspace(0, 255, 640).astype(np.uint8)
ys = np.linspace(0, 255, 640).astype(np.uint8)
grad[:, :, 0] = xs[None, :]
grad[:, :, 1] = ys[:, None]
grad[:, :, 2] = 128
Image.fromarray(grad, "RGB").save(f"{OUT}/synth_gradient.jpg", quality=95)

img = Image.new("RGB", (640, 640), (135, 160, 180))
d = ImageDraw.Draw(img)
d.rectangle([120, 300, 520, 470], fill=(60, 60, 65))
d.rectangle([150, 470, 490, 520], fill=(20, 20, 20))
d.ellipse([160, 500, 230, 560], fill=(10, 10, 10))
d.ellipse([410, 500, 480, 560], fill=(10, 10, 10))
d.rectangle([260, 430, 380, 465], fill=(230, 230, 220))
d.rectangle([260, 430, 380, 465], outline=(0, 0, 0), width=2)
img.save(f"{OUT}/synth_fake_vehicle_scene.jpg", quality=95)

print("Wrote synthetic inputs to", OUT)
for f in sorted(os.listdir(OUT)):
    print(" -", f)
