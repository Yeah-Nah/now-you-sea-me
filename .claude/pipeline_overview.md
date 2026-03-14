# Pipeline Overview — oakd-camera-tracking

Reference document for AI assistant context. Describes the current state of the pipeline as of March 2026.

---

## Project Summary

Edge device pipeline for live boat detection and tracking using an OAK-D camera and a custom YOLO model. Runs on a development laptop today; designed to be portable to a Raspberry Pi with config changes only. Next phase: attach Pi + OAK-D to a Waveshare UGV Rover for autonomous object following and obstacle avoidance.

---

## Repo Structure

```
now-you-sea-me/
├── .claude/
│   └── pipeline_overview.md    ← this file
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
│       │   ├── camera_access.py      ← DepthAI hardware layer (StereoDepth now wired)
│       │   ├── camera_recording.py   ← video + gyro recording to disk
│       │   └── camera_tracking.py    ← YOLO result annotation/drawing
│       ├── inference/
│       │   └── object_detection.py   ← YOLO model wrapper
│       ├── depth_perception/
│       │   ├── __init__.py           ← package init
│       │   ├── target_estimator.py   ← distance + bearing per detection ✅
│       │   └── depth_zones.py        ← obstacle zone analysis (placeholder) ✅
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
- **Stereo depth node:** `dai.node.StereoDepth` is now wired up in `_build_pipeline()`. CAM_B feeds `stereo.left`, CAM_C feeds `stereo.right`. Configured with `HIGH_DENSITY` preset and `setDepthAlign(CAM_A)` so the depth map is reprojected to match the colour camera's field of view exactly — bounding box pixel coordinates from the colour frame can be used directly on the depth map without rescaling. Depth output queue is stored as `self._depth_queue` (maxSize=8, non-blocking). Only built when both CAM_B and CAM_C are present.
- **IMU node:** created only if `record_gyroscope=True`. Enables `GYROSCOPE_RAW` at 100 Hz. Queue depth 50.
- `get_frame(cam_name)` → returns an OpenCV BGR/grayscale frame via `getCvFrame()`.
- `get_depth_frame()` → returns the latest depth frame as `NDArray[np.uint16]` where pixel values are distances in millimetres. Returns `None` if the stereo node was not wired or no frame is ready yet.
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

### `depth_perception/target_estimator.py` — `TargetEstimator`
Estimates distance and bearing for each YOLO detection using a stereo depth frame.
- Stateless — single instance reused across frames.
- Main method: `estimate(depth_frame, results, image_width) -> list[dict]`
- **Distance:** crops the inner 20% of each bounding box (40% edge crop on each side, via `_EDGE_CROP = 0.4`). Filters invalid pixels (`< 1mm` or `> 10,000mm`). Takes `np.median` of valid pixels and converts to metres. If fewer than 10 valid pixels remain, `distance_m` is set to `None` to signal low confidence.
- **Bearing:** normalised horizontal offset — `(box_centre_x - image_width / 2) / (image_width / 2)`. Range is [-1.0, +1.0]: negative = left of centre, positive = right of centre, 0 = dead ahead.
- Returns one dict per detection with keys: `track_id`, `confidence`, `distance_m`, `bearing_normalised`, `bbox_xyxy`.
- Constants: `_MIN_DEPTH_MM = 1`, `_MAX_DEPTH_MM = 10_000`, `_MIN_VALID_PIXELS = 10`, `_EDGE_CROP = 0.4`.

**Current integration status:** `TargetEstimator` is not yet called from `pipeline.py`. The module exists and is correct but `_apply_inference()` has not been updated to call `get_depth_frame()` or pass estimates to `CameraTracking`.

### `depth_perception/depth_zones.py` — `DepthZoneAnalyser` (placeholder)
Classifies obstacle danger across three horizontal zones of the depth frame. Intended for future connection to the ROS2 `control_node` / `obstacle_avoidance_node` — **not yet wired to anything in the pipeline**.
- Constructor accepts `danger_threshold_m: float = 2.0`.
- `analyse(depth_frame) -> dict` divides the frame into equal-width left / centre / right columns. For each zone: filters invalid pixels, computes minimum valid depth in metres, classifies as `"danger"` (below threshold), `"clear"`, or `"unknown"` (no valid pixels).
- Output format:
  ```python
  {
      "left":   {"min_depth_m": float | None, "status": "clear" | "danger" | "unknown"},
      "centre": {"min_depth_m": float | None, "status": "clear" | "danger" | "unknown"},
      "right":  {"min_depth_m": float | None, "status": "clear" | "danger" | "unknown"},
  }
  ```

---

## Data Flow (current state)

```
OAK-D Device
  ├── CAM_A (colour, 1920×1080) ──→ video queue ──→ get_frame("CAM_A") ──→ YOLO inference ──→ annotated frame ──→ record / display
  ├── CAM_B (mono,  640×400)   ──→ video queue ──→ get_frame("CAM_B") ──→ (no inference)  ──→ record / display
  ├── CAM_C (mono,  640×400)   ──→ video queue ──→ get_frame("CAM_C") ──→ (no inference)  ──→ record / display
  ├── CAM_B + CAM_C ──→ StereoDepth node ──→ depth queue ──→ get_depth_frame() ──→ (not yet consumed by pipeline)
  └── IMU (GYROSCOPE_RAW 100Hz)──→ imu queue   ──→ get_gyro_data()    ──→ JSONL recording
```

**Wired but not yet integrated:** `get_depth_frame()` produces depth frames, and `TargetEstimator` + `DepthZoneAnalyser` are implemented and correct, but `pipeline.py` does not yet call them. The next pending changes are:
1. Update `_apply_inference()` in `pipeline.py` to call `get_depth_frame()` and pass the result to `TargetEstimator.estimate()`.
2. Update `CameraTracking.draw_detections()` to accept estimates and overlay distance labels via `cv2.putText()`.
3. Update `_process_frame()` in `pipeline.py` so live view (`cv2.imshow`) only shows the colour camera (CAM_A), not all three cameras.

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

## Planned Next Steps

Three pending changes remain from the depth perception work:

1. **Integrate `TargetEstimator` into `pipeline.py`:** update `_apply_inference()` to call `self._camera.get_depth_frame()` and pass the depth frame + results to `TargetEstimator.estimate()`. Pass the returned estimates list to `CameraTracking.draw_detections()`.
2. **Overlay distance on live view:** update `CameraTracking.draw_detections()` to accept an optional `estimates: list[dict] | None` parameter and use `cv2.putText()` to draw `"{distance_m:.2f}m"` labels in cyan above each bounding box.
3. **Restrict live view to colour camera only:** update `_process_frame()` in `pipeline.py` so `cv2.imshow()` is only called when `self._camera.is_colour_camera(frame)` is True. All cameras continue to be recorded to disk.

Future modules planned for `depth_perception/`:
- `fusion.py` — IMU + depth fusion helpers (Phase 4)
