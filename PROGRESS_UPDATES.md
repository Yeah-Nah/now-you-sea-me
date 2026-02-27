# The Process: Building Where The Hull Are You

A development journey blog documenting the creation of a boat tracking system.

# Phase 0: Creating Pipeline on Local Device

## Entry 2: DepthAI V3 Migration & Gyroscope Integration
*Date: February 27, 2026*

Successfully migrated the camera pipeline to **DepthAI V3 API** and integrated gyroscope data recording:

**DepthAI V3 API Updates:**
- Migrated from `ColorCamera` node to new `Camera` node with `.build()` pattern
- Updated camera resolution to 1280x720 with increased output queue (16 frames)
- Fixed IMU sensor initialization to use list syntax: `enableIMUSensor([dai.IMUSensor.GYROSCOPE_RAW], 100)`
- Debugged device connection lifecycle and resource management

**Gyroscope Data Recording:**
- Implemented `GyroRecorder` class for timestamped gyroscope data logging
- Records gyro readings to JSONL format alongside video recordings
- Integrated IMU data capture with main pipeline loop
- Added `record_gyroscope` config toggle for optional gyro recording

**Key Learnings:**
- OAK-D IMU (BMI270) requires proper API syntax for sensor enablement
- V3 API breaking changes required careful queue management refactoring
- Device connection errors traced to Jupyter notebook sessions holding camera locks
- Queue configuration (batch thresholds, max reports) critical for real-time data flow

Pipeline now successfully captures synchronized video and gyroscope data streams when `record_gyroscope: True` in config.

Images of testing the video stream from the camera when running the pipeline from the command line, and testing the gyro data capture.

<img src="other\images\Screenshot 2026-02-26 203635.png" alt="Testing Camera Connection" width="600">

<img src="other\images\Screenshot 2026-02-26 205240.png" alt="Testing Camera Connection" width="600">

## Entry 1: Core Pipeline Architecture Implementation
*Date: February 23, 2026*

Built the complete pipeline for OAK-D camera, YOLO inference, tracking, and video recording:

- Camera access with optional gyroscope data capture
- Video recording with timestamps
- YOLO inference with multi-frame tracking support
- Config-driven feature toggling (inference, tracking, recording, live view)
- Command-line entry point (`run_pipeline.py`)

**Raspberry Pi Portability Built In:**
- All device-specific settings (output paths, FPS, resolution) are config-driven
- No hardcoded paths—everything resolves relative to project root
- Modular class structure with clear separation (camera, inference, recording, tracking)
- DepthAI and ultralytics both run on Raspberry Pi without code changes
- Settings validation ensures configs are correct before pipeline starts

When Raspberry Pi parts arrive, deployment is simply: copy code to Pi, update config values for device/storage paths, and run `run_pipeline.py`.

---
