# now-you-sea-me

An edge device pipeline for live boat detection and tracking using an OAK-D camera and a custom-trained YOLO model.

### **Check out my progress updates here:** ([`👉 Progress Updates 👈`](PROGRESS_UPDATES.md))

## Overview

This project captures video from an OAK-D camera, optionally runs YOLO inference for boat detection, tracks detections across frames, and records the output. The pipeline is designed to run on a development machine (laptop) now and be portable to a Raspberry Pi edge device with configuration changes only.

## Current Status

- **Phase 0**: Core pipeline architecture implemented (camera access, inference, tracking, recording)
- **Raspberry Pi deployment**: Ready for deployment
- See [planning.md](planning.md) for detailed design notes
- See [PROGRESS_UPDATES.md](PROGRESS_UPDATES.md) for development updates

## Quick Start

### Development Machine

From the repo root:

```bash
# Install the package
pip install -e ./oakd-camera-tracking

# Run the pipeline
cd oakd-camera-tracking
python run_pipeline.py
```

Configure behavior in `configs/pipeline_config.yaml` (enable/disable inference, tracking, recording, live view, etc.)

## Raspberry Pi Setup

### 1. Install System Dependencies

SSH into your Raspberry Pi and run:

```bash
# Update system packages. Approx 10 min.
sudo apt update && sudo apt upgrade -y

# Install required system packages. Approx 2 min.
sudo apt install -y python3-pip python3-venv git cmake libusb-1.0-0-dev
sudo apt install -y libopencv-dev python3-opencv

# Install DepthAI and configure camera permissions
pip3 install depthai --break-system-packages
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 2. Transfer Project Files

From your development machine:

```powershell
# Using rsync (recommended - automatically excludes files per .gitignore)
rsync -avz --exclude-from='.gitignore' --exclude '.git' `
  C:/Users/alexa/git/now-you-sea-me/oakd-camera-tracking/ `
  yeah-nah@<PI_IP>:/home/yeah-nah/oakd-camera-tracking/

# Or using SCP (copies everything - not recommended if you have large recordings)
scp -r oakd-camera-tracking yeah-nah@<PI_IP>:/home/yeah-nah/
```

### 3. Install Python Dependencies

Back on the Pi via SSH:

```bash
cd ~/oakd-camera-tracking

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install project and dependencies
pip install -e .
```

### 4. Configure for Pi

Edit the configuration file:

```bash
nano configs/pipeline_config.yaml
```

Update these settings:
- `dev_or_pi: "pi"`
- `live_view_enabled: False` (if running headless)
- `camera_feed_output_dir: "/home/yeah-nah/recordings/"`

Create output directory:

```bash
mkdir -p /home/yeah-nah/recordings
```

### 5. Run on Pi

```bash
# Connect OAK-D camera to USB 3.0 port
python3 run_pipeline.py
```

### 6. Retrieve Recordings

From your development machine:

```powershell
scp yeah-nah@<PI_IP>:/home/yeah-nah/recordings/* ./output/recordings/
```

## Troubleshooting

#### The feed shuts down within a few seconds

Likely a "brownout" and the unit doesn't have enough power. Ensure using a USB 3.0 cable and try plugging into the back of your computer instead of the top.

#### SSH connection fails with "Could not resolve hostname raspberrypi.local"

Use the Pi's IP address instead of hostname, especially when connected via mobile hotspot.

#### Camera not detected on Pi

Ensure udev rules are properly installed and camera is connected to USB 3.0 port (blue port).
