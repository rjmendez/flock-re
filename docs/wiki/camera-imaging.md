# Camera & imaging

How the device physically captures frames and hands them to the [ALPR pipeline](alpr-pipeline.md).

- **Capture path:** `CaptureSession.onFrame` → native `ImageUtils` JNI. Frame width/height are
  fixed per sensor model (`DeviceType`), not attacker-chosen at the API boundary — though the
  native size check itself is unsafe (see [ALPR pipeline](alpr-pipeline.md)).
- **Stack:** Qualcomm QCamera HAL + stock MSM camera device-tree bindings; no custom Flock camera
  kernel driver.
- **Day/night:** IR LEDs are driven for night capture; on the Falcon board an IR-cut-filter GPIO
  is reserved in the pin map but never actually driven. A privileged IR-LED brightness setter has
  an inverted file-existence check versus its app-layer sibling (a latent bug).
- **Compute:** the CV pipeline is **CPU-only** — no Hexagon/ADSP offload (the DSP partition has no
  CV code and the FastRPC driver is absent). See [ML models](ml-models.md).
- **Reliability:** the hardware has a chronic stuck-camera-IRQ fault that Flock works around with
  a kernel watchdog (force-kills the camera daemons) plus a userland `reaperd` — engineered
  around, not fixed. See [Kernel & drivers](kernel.md).

## See also
- [ALPR pipeline](alpr-pipeline.md) · [Kernel & drivers](kernel.md) · [Hardware](hardware.md)
