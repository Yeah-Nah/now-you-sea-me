## Project Overview
This project connects to an OAK-D camera, runs a YOLO model for boat detection, tracks detections across frames, and records video output based on configuration. The code is designed to be runnable on a development machine now and transferable to a Raspberry Pi edge device later with minimal changes.

## High-Level Goals
- Provide a clean, reusable pipeline for camera access, inference, tracking, and recording.
- Keep implementation minimal and focused on core functionality.
- Use configuration files to control behavior across environments (dev vs Raspberry Pi).
- Ensure outputs can be saved to local storage for later use.

## Core Workflow (High Level)
- Load configuration (model + pipeline).
- Initialize DepthAI camera pipeline and connect to the OAK-D device.
- For each frame: optionally run inference, optionally draw tracking overlays, optionally write to video output.
- Optionally capture gyroscope data and save alongside recordings.
- Clean shutdown with safe device release and file flush.

## Repository Structure (High Level)
- `configs/` contains YAML config files that define model and pipeline settings.
- `src/` contains reusable project code.
- `src/camera/` handles camera access, tracking overlays, and recording responsibilities.
- `src/inference/` contains the YOLO inference logic.
- `src/utils/` contains config utilities and validation helpers.
- `src/pipeline.py` orchestrates the flow between camera, inference, tracking, and recording.
- `run_pipeline.py` is the entry point to run the full pipeline from the command line.
- `models/` stores YOLO model files.
- `output/` stores recordings and any generated artifacts.

## Configuration Expectations
- The pipeline should be controlled by config values (enable/disable tracking, recording, live view, output paths).
- Inference should be optional so the pipeline can record raw camera feed without running the model.
- Model selection and inference settings should come from the model config file.
- Default output should be in `output/` with timestamped file names.
- Configs should support dev vs Raspberry Pi settings without code changes.
- Keep config keys stable and documented to avoid breaking the pipeline.

## Config Keys (High Level)
Keep the config schema stable. Expected keys (names can vary as long as intent is preserved):
- camera: fps, resolution, color/mono selection, optional preview/visualize flag.
- pipeline: inference_enabled, tracking_enabled, recording_enabled, live_view_enabled.
- recording: output_dir, file_prefix, container/codec, segment_length (optional).
- sensors: record_gyroscope (boolean to enable IMU capture).
- model: model_path, input_size, labels_path, confidence_threshold.
- runtime: device_target (dev vs pi), logging_level.

## Inputs and Outputs (High Level)
- Inputs: OAK-D camera stream and the YOLO model weights.
- Outputs: recorded video files, optional overlays if tracking is enabled, optional gyroscope data when enabled.
- File naming: timestamp-based filenames for consistent ordering and traceability.

## Model Details (High Level)
- YOLO model format should be defined in config (path to weights and labels).
- Input size and confidence threshold are config-driven.
- Model loading should be validated before pipeline starts.

## Performance and Runtime Constraints (High Level)
- Provide reasonable defaults for FPS and resolution for both dev and Raspberry Pi.
- Favor stability over maximum throughput on Raspberry Pi.
- Pipeline should run headless without a display when required.

## Error Handling Expectations (High Level)
- Graceful failure if camera is not found or disconnects.
- Clear error if model file or labels file is missing.
- Ensure output directory is created if it does not exist.

## CLI Usage (High Level)
- `run_pipeline.py` is the single entry point.
- It should load a config file and run the pipeline based on those settings.

## Raspberry Pi Portability
- Keep device-specific values in config rather than code.
- Avoid hard-coded absolute paths.
- Keep the pipeline code modular so it can run the same way on a Pi with only config changes.

## Runtime Assumptions
- OAK-D is connected locally via USB and accessible by DepthAI.
- Recording should continue uninterrupted when enabled.
- Pipeline should be able to run headless (no display) on the Raspberry Pi.

## Implementation Notes
- Use `loguru` for logging instead of print.
- Keep tests minimal and only add what is required.
- Do not add extra features beyond the core tracking and recording pipeline.
- Favor clear class boundaries with minimal coupling between camera, inference, and recording.
- Keep the entry point thin; main logic should live in `src/`.
