# What the camera collects and sends

## The basics

The camera is designed to spot vehicles and license plates as it records video. It's built like a dashboard camera — it sits in one place, constantly watching the road. When it sees a vehicle or plate, it captures information about what it found and where.

This page explains what data the camera keeps, how it stores it, what information leaves the device, and how long things stick around.

## Metadata — the facts about each vehicle

When the camera sees a vehicle, it records a bundle of details about the detection. Think of it like a digital notecard for each sighting:

- **Where it happened:** the camera records the GPS location — latitude, longitude, altitude, and accuracy — at the moment of capture. This is precise location information, like coordinates on a map.
- **What the camera saw:** structured information about each detected object — whether it spotted a vehicle, a license plate, or both, along with a confidence score (how sure the system is) and a quality score.
- **Where in the frame:** bounding boxes — invisible rectangles that mark exactly where on the video the plate or vehicle appears.
- **Camera settings:** camera parameters like the sensor's sensitivity (ISO), whether it was daytime or nighttime, exposure time, and white balance adjustments.
- **Identifying info:** the camera's serial number, model, and type.
- **Timestamp:** when the capture happened.

This metadata is stored in separate database records, not embedded inside the video files themselves.

## Video storage — encrypted but with the key in plain sight

Videos are stored as MP4 files on the device, and they are encrypted. Encryption is the process of scrambling data so that only someone with the right key can unscramble and read it.

**The problem:** the encryption key sits right next to the encrypted video files, in plain text. Plain text means it's not secret — it's like putting the key to your safe on a sticky note taped to the safe. Anyone who has physical access to the device can read the key and decrypt all the videos. The encryption provides no real protection against someone who can hold the device in their hands.

Videos typically account for about 13 gigabytes of the device's 18-gigabyte capture storage. That's roughly 27,000 video files.

## Plate reading happens in the cloud

Here's a key point: **the camera does NOT read license plate numbers**.

What the camera *does* do on-device:
- It *detects* that a plate is visible in the frame
- It *locates* where the plate is (the bounding box)
- It scores the quality of what it sees

What it *doesn't* do on-device:
- It does not convert the plate image into text (this process is called OCR — optical character recognition)
- It does not store or send plate numbers

The actual plate-number reading happens on the cloud servers after the video and metadata arrive. The device uploads a crop of the plate image, and the backend service processes that image to extract the characters.

## What leaves the device — and where

The camera sends data to vendor cloud servers. Specifically, it communicates with three endpoints:

1. **Device management APIs** (two versions, legacy and current) — for configuration, health status, and device control
2. **A binary upload socket** (a dedicated connection over TLS, which is encrypted transport) — for sending video files and their metadata

### The upload package

Per captured vehicle, the device sends:
- The MP4 video file itself
- Location information (GPS coordinates and accuracy)
- Metadata about each detected object (plate and vehicle detections, confidence, quality, bounding boxes)
- Camera information (model, serial number, settings used)
- Session and asset information (timestamps, IDs to track what belongs together)

### What else goes out

The camera also sends:
- **Telemetry and health data:** battery voltage, storage wear, firmware version, whether encryption is enabled (though remember — the key is in the clear). This happens regularly as a ~36-kilobyte payload.
- **Crash logs:** diagnostic bundles when the software encounters errors or exceptions. These are compressed (like a zip file) and stored locally first, but if the device syncs with the backend, the logs ship out too.

### What stays local

Your precise GPS location (not the camera's fixed location) does not leave the device. The camera does not perform any hotlist/watchlist matching locally — that "wanted plate" checking happens entirely on the cloud side.

## Privacy controls in the video

The camera applies some automatic privacy protections:

- **Blur:** the device blurs people's faces and bodies in about 47% of the recorded videos
- **Dehaze:** it applies image enhancement to about 19% of videos to improve visibility

## How long videos are kept

Videos are not kept forever. The camera has two cleanup policies:

1. **Age:** older videos get deleted after a certain time period
2. **Disk space:** when the storage fills up to about 85% full, the oldest videos are removed to make room for new ones

## The bottom line

The camera continuously watches the road and records video. For each vehicle it sees, it collects rich metadata — location, detection details, camera settings. It uploads videos and metadata to cloud servers regularly. Plate numbers are read in the cloud, not on the device. Stored videos are encrypted, but the encryption key is stored unprotected next to them. Videos are not kept permanently — they're removed as the disk fills up or time passes.

---

## Go deeper

For the technical details behind this summary, see:

- **[data-and-storage.md](data-and-storage.md)** — How the device physically stores data, partition layout, encryption details, and database schemas
- **[backend-protocol.md](backend-protocol.md)** — The exact protocols and messages the camera uses to communicate with the cloud, authentication methods, and the telemetry payload structure
- **[crash-logs.md](crash-logs.md)** — What diagnostic data is collected in crash bundles and how frequently it's generated
- **[alpr-pipeline.md](alpr-pipeline.md)** — The detailed stages of license-plate detection and localization on-device, and where OCR happens
- **[camera-imaging.md](camera-imaging.md)** — How the camera hardware physically captures frames and the imaging pipeline
