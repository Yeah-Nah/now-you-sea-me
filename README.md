# now-you-sea-me

An edge device pipeline for live boat detection and tracking using an OAK-D camera and a custom-trained YOLO model.

### **Check out my progress updates here:** ([`👉 Progress Updates 👈`](PROGRESS_UPDATES.md))

## Overview

This project captures video from an OAK-D camera, optionally runs YOLO inference for boat detection, tracks detections across frames, and records the output. The pipeline is designed to run on a development machine (laptop) now and be portable to a Raspberry Pi edge device with configuration changes only.

## Current Status

- **Phase 0**: Core pipeline architecture implemented (camera access, inference, tracking, recording)
- **Next Steps**: Deploy to Raspberry Pi once hardware arrives
- See [planning.md](planning.md) for detailed design notes
- See [PROGRESS_UPDATES.md](PROGRESS_UPDATES.md) for development updates

## Quick Start

From the `oakd-camera-tracking/` directory:

```bash
python run_pipeline.py
```

Configure behavior in `configs/pipeline_config.yaml` (enable/disable inference, tracking, recording, live view, etc.)

## Troubshooting

#### The feed shuts down within a few seconds

Likely a "brownout" and the unit doesn't have enough power. Ensure using a USB 3.0 cable and try plugging into the back of your computer instead of the top.
