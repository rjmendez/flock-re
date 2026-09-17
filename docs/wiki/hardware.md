# Hardware

A screenless Android device on a pole. Compute is a pre-certified COTS system-on-module.

- **SoC:** Qualcomm MSM8953 / APQ8053 (Snapdragon 62x class), 8× Cortex-A53, 14nm.
- **Module:** Lantronix/Intrinsyc Open-Q 624A SoM (`ro.product.board=OPENQ_624A`).
- **OS:** [Android 8.1.0 Oreo](android-userland.md) (API 27).
- **Connectivity:** integrated LTE modem + eSIM; on-board GNSS — see [Cellular & location](cellular-and-location.md).
- **Optics:** camera + IR LED array (PWM-driven) for night capture.
- **Power:** solar + battery via a TI BQ24650 charge controller; battery heater for cold.

## See also
- [Partition map](partition-map.md) · [Security posture](security-posture.md)
