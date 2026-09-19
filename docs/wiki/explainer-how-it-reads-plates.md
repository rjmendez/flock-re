# How the Camera Spots and Reads License Plates

A Flock camera is designed to capture video of traffic and automatically extract license plate numbers. Here's how it actually works — and a key fact that often surprises people: **the camera doesn't read the plate numbers itself. It sends cropped photos to Flock's servers, where the actual reading happens.**

## Capturing the Video

The camera uses a standard Qualcomm processor and image sensor to capture frames continuously. When it's dark, infrared LEDs turn on to light up the scene (like a security camera). The frames come off the sensor in YUV format — a way of storing color and brightness information that cameras use internally.

Right away, those frames get converted to RGB (the color format most software uses) and resized for processing. This all happens inside the camera device.

## Spotting What's in the Scene

The camera runs **machine-learning models** (TensorFlow Lite models, to be precise) that process each frame. These models are trained to recognize objects.

Specifically, the camera looks for:
- **License plates** (the main target)
- **Vehicles** (cars, trucks, motorcycles, bicycles)
- **People**

The models work like a trained spotter: they scan the frame and output a list of "I found a plate-like thing at coordinates X,Y" or "there's a person at X,Y." Each detection comes with a confidence score — how sure the model is.

This detection and localization step **happens entirely on the camera device**. No data leaves yet.

## Filtering for Quality

Not every detection makes the cut. The camera runs additional code (Qualcomm FastCV, a computer-vision library) to score the quality of each candidate. License plates have a very high bar: the model must be at least 98% confident. People and vehicles are kept even at much lower confidence (1%).

The camera also tracks detections across multiple video frames — if it sees the same plate-shaped object in frame 1, frame 2, and frame 3, it gains more confidence that it's real. The camera picks the single best crop (the clearest, most confident view) and marks it as an "asset" to upload.

## The Crucial Part: Reading Happens in the Cloud

Here's the key: **the camera never actually reads the license plate number**. There is no code on the camera that converts the image into text — no on-device OCR (Optical Character Recognition).

Instead, the camera:
1. Detects and locates the plate (on-device)
2. Crops out that region
3. **Sends the cropped image to Flock's servers**

The servers run the OCR step — they take the image and output the plate number as text. This happens off-device, in Flock's data center.

Why this design? On-device resources are limited. OCR is computationally expensive and needs access to Flock's plate datasets to handle different states and formats. The cloud handles that complexity.

## What Gets Stored

Along with each vehicle detection, the camera records:
- A bounding box (the rectangle around the vehicle and license plate)
- A quality score
- A tracking ID (which vehicle this is across multiple frames)
- Direction (is the vehicle heading left or right)
- Class label (person, vehicle, bicycle, etc.)

Notably, **the actual plate text is not stored on the camera**. It only exists after the servers do the OCR.

For video storage, the system applies privacy filters to roughly 47% of videos (a blur) and de-hazing to about 19%. Videos are encrypted on the device, though the encryption key sits in the firmware (not hidden). Retention is governed by disk space and age limits.

## Detection Without Matching

One thing the camera does **not** do: match plates against "hotlists" or "wanted vehicle" lists. That matching happens entirely on the servers after OCR. The camera is purely a detector and uploader; the intelligence for matching comes from the backend.

## A Note on Trust

When evaluating this system, remember:
- The detection models are shipped as files in the firmware and can be inspected.
- No proprietary layers hide what the models do — they use standard TensorFlow operations only.
- The boot chain is test-signed (not production-signed), which has security implications if you're considering the device's integrity.

## Go Deeper

For the technical details:
- **[alpr-pipeline.md](alpr-pipeline.md)** — Complete breakdown of each stage (capture, convert, detect, read, track).
- **[ml-models.md](ml-models.md)** — What detection models ship, what classes they recognize, test results.
- **[camera-imaging.md](camera-imaging.md)** — Hardware and image-capture specifics, the imaging stack.
