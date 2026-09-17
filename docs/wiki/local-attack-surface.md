# Local attack surface

On-device components reachable by other apps/processes, and remote-debug paths. Static findings;
no exploitation performed.

## Exported components (high/critical)
- **Auth service, no permission.** The OAuth key service ([`flock-sambuca`](apps.md)) is declared
  `exported="true"` with no `android:permission`; its `onBind` returns the binder
  unconditionally, so any app can request live tokens/client secrets from it. The app runs as
  `system` UID and is `persistent`.
- **Unauthenticated broadcast.** A receiver registered with the 2-arg `registerReceiver()` (no
  permission) accepts a broadcast that persists attacker-supplied client credentials as the
  device's sign-in identity — i.e. any on-device sender can overwrite the camera's identity.

## Remote debug
- **ADB-over-Wi-Fi** is gated by a custom system property (`vendor.flock.adb-wifi`) that flips
  ADB to TCP and restarts the daemon — but by itself grants no shell/root: `ro.adb.secure=1`
  (RSA key auth) and a `user` build still apply. So it's a foothold enabler, not instant access.

## FastRPC / DSP (not exposed here)
- The FastRPC/`adsprpc` **kernel module is absent** from the image, so that classic Snapdragon
  privilege-escalation path can't load on this build. `/dev/adsprpc-smd` node permissions are
  loose (an open question), but no live invocation path into the CV/DSP stack was found.

## Sockets
- 24 local sockets across init scripts are all stock Qualcomm BSP; none touch FastRPC/ADB/ALPR.

## See also
- [Apps](apps.md) · [Backend protocol](backend-protocol.md) · [Security posture](security-posture.md)
