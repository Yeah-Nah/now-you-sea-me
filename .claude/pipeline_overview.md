# Pipeline Overview — oakd-camera-tracking

Reference document for AI assistant context. Describes the current state of the pipeline as of March 2026.

---

## Project Summary

Edge device pipeline for live boat detection and tracking using an OAK-D camera and a custom YOLO model. Runs on a development laptop today; designed to be portable to a Raspberry Pi with config changes only. Next phase: attach Pi + OAK-D to a Waveshare UGV Rover for autonomous object following and obstacle avoidance.

---

## Repo Structure

```
now-you-sea-me/
├── oakd-camera-tracking/       ← main package
│   ├── run_pipeline.py         ← entry point
│   ├── configs/
│   │   ├── pipeline_config.yaml
│   │   ├── model_config.yaml
│   │   └── camera_config.yaml
│   ├── models/
│   │   └── 18ft_skiff_yolo11n_20260210_195721.pt   ← custom YOLO11n model
│   ├── output/recordings/      ← saved video + JSONL gyro data
│   └── src/
│       ├── pipeline.py         ← orchestrator
│       ├── settings.py         ← config loading + validation
│       ├── camera/
│       │   ├── camera_access.py      ← DepthAI hardware layer
│       │   ├── camera_recording.py   ← video + gyro recording to disk
│       │   └── camera_tracking.py    ← YOLO result annotation/drawing
│       ├── inference/
│       │   └── object_detection.py   ← YOLO model wrapper
│       ├── depth_perception/
│       │   └── __init__.py           ← placeholder, work in progress
│       └── utils/
│           └── config_utils.py       ← YAML loading, project root resolution
├── planning.md                 ← full phase plan (Phases 0–5)
└── PROGRESS_UPDATES.md
```

---

## Entry Point

`run_pipeline.py` — parses CLI args for config paths (defaults to `configs/*.yaml`), constructs `Settings`, constructs `Pipeline`, calls `pipeline.run()`.

```
python run_pipeline.py
python run_pipeline.py --pipeline-config configs/pipeline_config.yaml
                       --model-config    configs/model_config.yaml
                       --camera-config   configs/camera_config.yaml
```

---

## Configuration

### `pipeline_config.yaml`
| Key | Default | Effect |
|---|---|---|
| `dev_or_pi` | `"dev"` | Target environment flag |
| `live_view_enabled` | `True` | Show camera feed in OpenCV window |
| `recording_enabled` | `True` | Write video frames to disk |
| `inference_enabled` | `False` | Run YOLO detection on frames |
| `record_gyroscope` | `True` | Capture IMU gyro data to JSONL |
| `camera_feed_output_dir` | `"output/recordings/"` | Output directory |

### `model_config.yaml`
| Key | Value |
|---|---|
| `model` | `18ft_skiff_yolo11n_20260210_195721.pt` |
| `conf` | `0.7` |
| `classes` | `[0]` (boat class) |
| `persist` | `True` (multi-frame tracking enabled) |
| `verbose` | `False` |

### `camera_config.yaml`
| Key | Value |
|---|---|
| `colour_camera_resolution` | `[1920, 1080]` (CAM_A, reduced from native 4K for USB bandwidth) |
| `mono_camera_resolution` | `[640, 400]` (CAM_B and CAM_C, native resolution) |

---

## Module Responsibilities

### `settings.py` — `Settings`
- Loads all three YAML configs at init.
- Resolves relative paths to absolute paths anchored at the project root (determined from `config_utils.py`).
- Validates that the model file exists (if inference enabled) and that a display is available (if live view enabled).
- Exposes all config values as typed properties.

### `pipeline.py` — `Pipeline`
The central orchestrator. Owns the main loop and wires all components together.

**Init:** creates `CameraAccess`, `CameraTracking` (if inference on), `ObjectDetection` (if inference on), `GyroRecorder` (if gyro on).

**`run()`:** starts camera → sets up per-camera recorders → enters main loop → shuts down cleanly.

**Main loop `_main_loop()`:**
```
for each camera:
    get frame
    _process_frame(cam_name, frame)
        → lazy-start video recorder on first frame
        → lazy-start gyro recorder (synced to primary camera timestamp)
        → _apply_inference(frame) → annotated frame
        → write frame to recorder
        → show in OpenCV window (if live_view_enabled)
poll gyro queue → flush readings to JSONL
check for 'q' keypress to quit
```

**Shutdown:** stops all recorders, stops camera, destroys OpenCV windows.

### `camera/camera_access.py` — `CameraAccess`
The DepthAI hardware layer. Key behaviours:
- On `start()`: opens a temporary device connection to **discover cameras dynamically** (socket name, sensor type, native resolution). Closes the temp connection, then builds the real DepthAI pipeline.
- **Camera nodes:** one `dai.node.Camera` per discovered sensor. CAM_A is colour (1920×1080), CAM_B and CAM_C are mono (640×400, the stereo pair).
- **IMU node:** created only if `record_gyroscope=True`. Enables `GYROSCOPE_RAW` at 100 Hz. Queue depth 50.
- **Current limitation:** stereo depth (`dai.node.StereoDepth`) is NOT yet wired up. CAM_B and CAM_C exist as individual video queues only; they are not combined into a depth map yet. This is the planned work for `depth_perception/`.
- `get_frame(cam_name)` → returns an OpenCV BGR/grayscale frame via `getCvFrame()`.
- `get_gyro_data()` → returns list of `{timestamp_s, x, y, z}` dicts from the latest IMU packet.

### `camera/camera_recording.py` — `CameraRecording` + `GyroRecorder`
- `CameraRecording`: wraps an `cv2.VideoWriter`. Timestamped filename. Started lazily on first frame so frame dimensions are known. Writes each frame via `write()`. `stop()` releases the writer.
- `GyroRecorder`: writes gyro readings to a `.jsonl` file. Filename timestamp is synced to the primary camera's recording timestamp so both files can be aligned in post-processing.

### `camera/camera_tracking.py` — `CameraTracking`
Stateless. Single method `draw_detections(frame, results)` calls `results.plot()` to generate an annotated frame with bounding boxes and track IDs drawn. The `frame` argument is accepted for API compatibility but the annotated output comes from YOLO directly.

### `inference/object_detection.py` — `ObjectDetection`
Wraps the YOLO model.
- Loads the `.pt` model file with ultralytics `YOLO`.
- `run(frame)`: calls `model.track()` when `persist=True` (multi-frame tracking), otherwise `model.predict()`.
- Returns a single `Results` object or `None` on failure.
- Config keys forwarded to YOLO: `conf`, `classes`, `persist`, `verbose`.

### `utils/config_utils.py`
- `get_project_root()`: resolves from `__file__` location (3 levels up from `src/utils/`).
- `load_yaml(path)`: loads and validates a YAML file, raises on missing or empty file.

### `depth_perception/` — Work In Progress
Package exists (`__init__.py` created). No modules yet. Planned contents:
- `depth_zones.py` — obstacle zone analysis (left/centre/right zone danger classification from depth map)
- `target_estimator.py` — 3D target position from bounding box + depth (Phase 2/3)
- `fusion.py` — IMU + depth fusion helpers (Phase 4)

This package will **consume** depth frames produced by `camera_access.py` (once the `StereoDepth` node is wired in). It does not interact with the camera hardware directly.

---

## Data Flow (current state)

```
OAK-D Device
  ├── CAM_A (colour, 1920×1080) ──→ video queue ──→ get_frame("CAM_A") ──→ YOLO inference ──→ annotated frame ──→ record / display
  ├── CAM_B (mono,  640×400)   ──→ video queue ──→ get_frame("CAM_B") ──→ (no inference)  ──→ record / display
  ├── CAM_C (mono,  640×400)   ──→ video queue ──→ get_frame("CAM_C") ──→ (no inference)  ──→ record / display
  └── IMU (GYROSCOPE_RAW 100Hz)──→ imu queue   ──→ get_gyro_data()    ──→ JSONL recording
```

**Not yet wired:** CAM_B + CAM_C → `StereoDepth` node → depth map → `depth_perception/` module.

---

## What YOLO Returns

`results.boxes` contains per-detection:
- Bounding box (xyxy pixel coords in the colour frame)
- Confidence score
- Class ID
- Track ID (when `persist=True`)

Currently only the colour frame (CAM_A) goes through YOLO. Depth is not yet associated with detections.

---

## Output Files

Saved to `output/recordings/`, timestamped per session (`YYYYMMDD_HHMMSS`):
- `cam_a_recording_<timestamp>.mp4` — colour camera video
- `cam_b_recording_<timestamp>.mp4` — left mono video
- `cam_c_recording_<timestamp>.mp4` — right mono video
- `gyro_<timestamp>.jsonl` — IMU gyro readings `{timestamp_s, x, y, z}` per line

---

## Key Design Decisions

- **Dynamic camera discovery:** cameras are not hardcoded. The pipeline queries the device at runtime for connected sockets and their capabilities. This means the pipeline adapts if the hardware changes.
- **Lazy recorder init:** recorders are opened on the first frame so that frame dimensions do not need to be hardcoded.
- **Gyro timestamp sync:** the JSONL gyro file shares its timestamp with the primary camera's video file, enabling post-processing alignment.
- **Stateless tracker:** `CameraTracking` holds no state. YOLO maintains its own internal track state when `persist=True`.
- **Inference is optional:** `inference_enabled: False` in config skips YOLO entirely. The pipeline runs as a plain recorder.

---

## Planned Next Step

Wire up `dai.node.StereoDepth` in `camera_access.py` using CAM_B and CAM_C as the stereo pair. Expose the resulting depth map via a new `get_depth_frame()` method. Build `depth_perception/depth_zones.py` to consume that depth map and classify obstacle zones, and `depth_perception/target_estimator.py` to associate detection bounding boxes with depth readings for 3D target positioning.
