# What These Cameras Are and What They Do

A Flock ALPR camera (short for Automatic License Plate Reader) is a surveillance device that sits on a pole and watches the road. Its job is to photograph every vehicle that passes by and read the license plate number.

## The Hardware: A Box on a Pole

The camera looks like a small black box mounted on a utility pole or street sign. It runs on Android, the same operating system that's inside smartphones. The device has:

- A regular camera lens for daytime recording
- An infrared light (IR) and LED array so it can see and record at night
- A cellular connection (LTE) so it can send data to the cloud
- Solar panels and a battery, plus a heater for winter
- GPS so it knows where it is

Think of it as a simplified phone without a screen: it can't display anything, but it can capture video, process images, and transmit data over the internet.

## What It Captures: Every Vehicle

The camera **records every vehicle that passes in front of it**—not just vehicles on a "wanted" list. It captures:

- Video of the car and the area around it
- The vehicle's shape, color, and size
- The license plate (the metal rectangle on the front and back)

The camera works day and night. During the day it uses regular light. At night it turns on the infrared LED to see in the dark.

## The Two-Step Process: Device + Cloud

Here's where it gets interesting. The camera does **not** read the plate number by itself. Instead, it works in two stages:

**Stage 1: On the Camera (Detection)**
The camera runs a small artificial-intelligence program on the device. This program scans the video for license plates and finds their exact location in the image. It's like someone pointing at a plate and saying, "There's a plate right here." The camera keeps track of which detection looks best.

**Stage 2: In the Cloud (Reading)**
The camera uploads a cropped image of the best plate it found, along with information like what time it captured the vehicle. The cloud servers—computers run by Flock—actually read what the plate says. This is called OCR (Optical Character Recognition). The device never stores or transmits the plate number itself. It only sends the picture.

## What Happens to the Data

After detecting a plate, the camera:

1. Stores a video clip and metadata (time, location, vehicle description) on the device
2. Encrypts the video file before storage
3. Uploads the video and metadata to Flock's cloud servers over an LTE connection
4. Deletes old recordings when the device runs out of storage space or after a certain amount of time

The camera keeps a local database of all the vehicles it's recorded. This database is uploaded to the cloud, but a copy stays on the device.

## How Much Data?

The camera might photograph hundreds of vehicles per day, even busy roads can show thousands. All that data includes:

- Video clips (encrypted before stored)
- Structured information for each detection: the plate location in the image, the time, location, vehicle color and type
- But **not** the actual plate number—only Flock's cloud system reads and stores that

## Privacy Note: It Photographs Everyone

This is important: the camera doesn't check a watchlist before recording. It doesn't know whether a vehicle is "wanted" or not. It just captures everyone. So even if you're doing nothing wrong, your vehicle's image is recorded and the plate is read and stored in Flock's system. This is called "bulk collection."

Law enforcement can then query the system ("show me all red sedans from June 3rd on Main Street") and use the matched vehicles for investigations. But the system captures the data first, regardless of whether there's any suspicion.

## Go Deeper

For more technical detail, see:

- **[hardware.md](hardware.md)** — the internal components and compute platform
- **[alpr-pipeline.md](alpr-pipeline.md)** — exactly how the detection and plate reading process works, including the native code layers
- **[security-posture.md](security-posture.md)** — technical security findings from analysis of the firmware
- **[data-and-storage.md](data-and-storage.md)** — where data lives on the device, how it's encrypted (and what that means)
- **[boot-chain.md](boot-chain.md)** — how the device starts up and what controls it
