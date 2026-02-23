# The Process: Building Where The Hull Are You

A development journey blog documenting the creation of a boat tracking system.

---

# Phase 0: Creating Pipeline on Edge Device

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
