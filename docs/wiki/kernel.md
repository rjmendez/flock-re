# Kernel & drivers

The Linux kernel, its config, and notable drivers.

- **Version:** Linux **3.18.71** (Qualcomm CAF `msm-3.18` branch, GCC 4.8), built 2025-06-05;
  the backup boot slot still runs a 2023 build. Upstream 3.18 has been **end-of-life since ~2018**,
  and the Android security-patch string is frozen at 2018-06-05 — see [Security posture](security-posture.md).
- **Config:** the full `.config` (4309 lines) is recoverable via in-kernel IKCONFIG.
- **Module signing enforced** end-to-end (`MODULE_SIG_FORCE`, SHA-512) — every `.ko` is signed to
  the running kernel. (A hardening bright spot amid the stale base.)
- **Flock kernel patch:** a GPIO/pinctrl watchdog detects a stuck camera IRQ and **force-kills
  `cameraserver`/`mm-qcamera-daemon`** to recover — an engineered workaround for a chronic camera
  fault (paired with a userland `reaperd` watchdog). See [Camera & imaging](camera-imaging.md).
- **Stock elsewhere:** IR-LED, power (BQ24650 charger), touch, and PMIC bindings use the generic
  Qualcomm MSM device-tree framework and stock drivers — no custom Flock kernel drivers there.
- Minor hardening gaps (`STRICT_DEVMEM` unset, regular not strong stack-protector) noted as
  informational.

## See also
- [Boot chain](boot-chain.md) · [Camera & imaging](camera-imaging.md) · [Security posture](security-posture.md)
