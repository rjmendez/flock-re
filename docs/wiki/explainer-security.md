# The Security Problems, in Plain Terms

## What This Camera Does

This is a camera system designed to detect license plates on passing vehicles. Here's the basic flow:

1. The camera films a passing car.
2. **On the device itself**, it finds and locates the license plate in the frame (like circling it in a photo).
3. It sends a cropped image of the plate to the cloud, where software reads the actual numbers.
4. It stores the video, plus some metadata (GPS location, when it happened, what it detected).

The videos are technically encrypted, but as you'll see, that encryption doesn't actually protect anything because of how it's built.

---

## The Five Core Problems

### 1. The Door Has an Open Lock

The device starts up using a **test key** — something like a generic demonstration key that Qualcomm ships with all of its reference hardware for developers. Normally, each device would have its own unique "real" key that only the manufacturer knows.

Here's the problem: the private version of this test key is public. Anyone can download it. That means anyone with physical access to the device can sign their own code and the device will boot it up and run it.

Additionally, the bootloader is **unlocked**. Think of the bootloader as a gatekeeper that decides which code is allowed to run. When it's unlocked, someone with the device can flash custom firmware over USB, no questions asked.

**Why it matters:** Someone holding the device for even a few minutes could install modified firmware that steals all the data, disables the camera, or reports false detections.

---

### 2. Passwords Sitting in Plain Text

Credentials — passwords, API tokens (secret keys used to authenticate to a service), OAuth tokens — are stored in plain text in the device's databases and configuration files. It's like writing your password on a sticky note and taping it to your monitor.

There are two separate storage areas:
- The device's regular encrypted data partition (the app data area) is encrypted properly with a key locked inside the hardware, so even with the device you can't decrypt it.
- But the system settings area (`persist`) keeps credentials as plain-text JSON files. The capture videos are encrypted, but the encryption key is stored **in plain text right next to the encrypted data** — on the same unencrypted partition.

**Why it matters:** Anyone with the device can read these credentials and use them to upload data, authenticate API calls, or impersonate the device to the cloud service.

---

### 3. Debuggable Apps (Left On for Production)

Almost every app on the device ships with a "debuggable" flag set to true. In Android, this is a developer feature that allows programmers to attach a debugger and step through the code line by line while it's running. It's like leaving the hood of your car open with the engine running and the keys in the ignition.

On a production device that's deployed in the field, debuggable apps should always be turned off. But here, they're on.

**Why it matters:** With debuggable apps, someone connected to the device (especially over ADB — a debugging protocol) can inspect and modify the running app's memory, call internal functions, and potentially hijack its behavior.

---

### 4. The Installer Wi-Fi Servicing Server

When the device is set up, it broadcasts a Wi-Fi network (like a mobile hotspot) so a technician can access it for configuration. This Wi-Fi uses a hardcoded password — the same password on every single device.

Once connected to that Wi-Fi, a technician can reach an HTTP web server running on the device. This server has **21 different commands** it responds to, and **none of them require any authentication.** No username, no password, no token check.

Some of these commands are:
- Turn on ADB (which gives remote code execution — the ability to run any command)
- Download all captured video and metadata
- Reboot the device
- See sensitive device identifiers (IMEI, IMSI, ICCID)
- Read the logs (which contain passwords and tokens)
- Change camera settings
- Disable the camera battery
- Flip power relays

Also, this server runs as `system` — the highest privilege level on Android.

And there's no rate limiting. Someone could hammer this server with 10,000 requests per second.

**Why it matters:** A person with the installer Wi-Fi password (which is the same on every device, so not really secret) can do almost anything to a device remotely — without needing physical access or any credentials.

---

### 5. A Second-Order Problem: Inter-App Communication Left Open

Android apps talk to each other through defined communication channels called "exported components." These require permissions, unless the developer leaves them wide open.

This device has several exported services with **no permission requirement**. For example:
- The OAuth token service is exported with zero protection — any app on the device (or any code running on the device) can request live tokens.
- A broadcast receiver lets any app overwrite the device's stored identity.
- Another exported service has a directory traversal bug that lets an app read files outside its intended area.
- A database export service copies the entire ALPR capture database to a world-readable location on a broadcast.

**Why it matters:** Any malicious app installed on the device, or any code injected through the debuggable apps, can steal credentials, overwrite identity, or exfil the entire database of captured plates and videos.

---

## Why These Matter Together

Each of these issues in isolation might be survivable (through manual management or organizational controls). But together, they form a layered failure:

1. **Boot-chain trust is broken** (test key + unlocked bootloader).
2. **On-device secrets are in plain text** (credentials and encryption keys).
3. **On-device code is debuggable** and many inter-app boundaries are open.
4. **The installation/servicing interface is completely unauthenticated** and has root privileges.

An attacker with a few minutes of physical access to a device can:
- Decrypt all stored video using the plaintext encryption key.
- Extract all credentials and use them to impersonate the device.
- Attach a debugger or install modified apps to intercept and alter behavior.
- Flash custom firmware that persists even after factory reset.

Someone with the installer Wi-Fi key (the same across all devices) can do much of this **remotely**, without ever touching the device.

---

## What the Device *Does* Protect

To be clear: the app data partition (`/data`) is genuinely encrypted with a hardware-bound key. If an attacker can't decrypt that, they can't access the app's internal settings or the system's encryption keys. That's real protection, and it's correctly implemented.

But the developers chose to protect **their own app data** better than they protected **the surveilled footage and its access credentials**.

---

## Go Deeper

For technical details, see:

- **[boot-chain.md](boot-chain.md)** — How the boot chain trusts test keys and why the bootloader being unlocked matters.
- **[security-posture.md](security-posture.md)** — A comprehensive inventory of all findings, rated by severity.
- **[local-attack-surface.md](local-attack-surface.md)** — Detailed breakdown of the servicing server and exported components.
- **[ota-updates.md](ota-updates.md)** — How firmware updates work and why the integrity chain is weak.
- **[data-and-storage.md](data-and-storage.md)** — Where secrets are stored and how the encryption actually works (and doesn't).
- **[alpr-pipeline.md](alpr-pipeline.md)** — How plate detection and reading work; what happens on-device vs. in the cloud.
