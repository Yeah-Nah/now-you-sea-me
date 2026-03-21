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
│       │   ├── camera_access.py      ← DepthAI hardware layer
│       │   ├── camera_recording.py   ← video + gyro recording to disk
│       │   └── camera_tracking.py    ← YOLO result annotation/drawing + depth overlay
│       ├── inference/
│       │   └── object_detection.py   ← YOLO model wrapper
│       ├── depth_perception/
│       │   ├── __init__.py           ← package init
│       │   ├── target_estimator.py   ← distance + bearing per detection ✅
│       │   └── depth_zones.py        ← obstacle zone analysis (placeholder)
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
| `recording_enabled` | `False` | Write video frames to disk |
| `inference_enabled` | `True` | Run YOLO detection on frames |
| `record_gyroscope` | `False` | Persist IMU gyro data to JSONL (IMU node is always active) |
| `camera_feed_output_dir` | `"output/recordings/"` | Output directory |

### `model_config.yaml`
| Key | Value |
|---|---|
| `model` | `yolo11n.pt` |
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

**Init:** creates `CameraAccess`, `CameraTracking` (if inference on), `ObjectDetection` (if inference on), `GyroRecorder` (if gyro on), `TargetEstimator` (if inference on). Also initialises `_colour_camera_names: set[str] = set()` (populated after `start()`), a shared `_session_timestamp` string (generated at init and used by both video recorders and the gyro recorder for aligned filenames).

**`run()`:** starts camera → populates `_colour_camera_names` from `get_colour_camera_names()` (hardware metadata, set once) → sets up per-camera recorders → enters main loop → shuts down cleanly.

**Main loop `_main_loop()`:**
```
poll gyro queue → flush readings to recorder (if record_gyroscope) and/or IMU integrator (if imu_cmc_enabled)
  → early return if both gyro recorder and IMU integrator are None (avoids unnecessary queue drain)
compute warp:
  → if imu_cmc_enabled: warp = ImuIntegrator.get_warp_and_reset()
       returns None if accumulated displacement < 0.5 px (no meaningful motion)
  → else: warp = None
for each camera:
    get frame
    _process_frame(cam_name, frame, warp)
        → lazy-start video recorder on first frame
        → lazy-start gyro recorder (synced to primary camera timestamp)
        → _apply_inference(frame, warp) if cam_name in _colour_camera_names else pass through
        → write frame to recorder
        → show in OpenCV window only if live_view_enabled AND cam_name in _colour_camera_names
check for 'q' keypress to quit
```

**`_apply_inference(frame, warp)`:**
```
if warp is not None:
    stabilise RGB frame with cv2.warpAffine (INTER_LINEAR, BORDER_REPLICATE)
run YOLO detector on (possibly stabilised) frame
get depth frame from camera
if warp is not None and depth frame available:
    stabilise depth frame with cv2.warpAffine (INTER_NEAREST, BORDER_REPLICATE)
    → brings depth map into the same coordinate space as the warped RGB frame
      so TargetEstimator samples the correct depth region for each bounding box
if depth frame available and estimator present:
    estimates = TargetEstimator.estimate(depth_frame, results, frame_width)
else:
    estimates = []
return CameraTracking.draw_detections(frame, results, estimates)
```

**Shutdown:** stops all recorders, stops camera, destroys OpenCV windows.

### `camera/camera_access.py` — `CameraAccess`
The DepthAI hardware layer. Key behaviours:
- On `start()`: opens a temporary device connection to **discover cameras dynamically** (socket name, sensor type, native resolution). Closes the temp connection, then builds the real DepthAI pipeline.
- **Camera nodes:** one `dai.node.Camera` per discovered sensor. CAM_A is colour (1920×1080), CAM_B and CAM_C are mono (640×400, the stereo pair).
- **Stereo depth node:** `dai.node.StereoDepth` wired in `_build_pipeline()`. CAM_B feeds `stereo.left`, CAM_C feeds `stereo.right`. Configured with `DEFAULT` preset, `setDepthAlign(CAM_A)`, and `setOutputSize(*colour_resolution)` so the depth map exactly matches the colour camera's frame dimensions — bounding box pixel coordinates from the colour frame can be used directly on the depth map without rescaling. Depth output queue stored as `self._depth_queue` (maxSize=8, non-blocking). Only built when at least two mono cameras and a colour camera are present.
- **IMU node:** always created unconditionally. Enables `GYROSCOPE_RAW` at 100 Hz, batch threshold 1, max batch reports 10. Queue depth 50. The `record_gyroscope` config flag only controls whether readings are persisted to disk — the IMU is always streaming.
- `get_frame(cam_name)` → returns an OpenCV BGR/grayscale frame via `getCvFrame()`.
- `get_colour_camera_names()` → returns a `set[str]` of socket names for all colour (RGB) sensors, derived from `_camera_features` hardware metadata. Only valid after `start()`.
- `is_colour_camera(frame)` → returns `True` if the frame has 3 channels (H, W, 3), used by `CameraRecording.start()` to choose between colour and grayscale VideoWriter modes.
- `get_depth_frame()` → returns the latest depth frame as `NDArray[np.uint16]` where pixel values are distances in millimetres. Returns `None` if the stereo node was not wired or no frame is ready yet.
- `get_gyro_data()` → returns list of `{timestamp_s, x, y, z}` dicts from the latest IMU packet, or `None` if no packet is available.

### `camera/camera_recording.py` — `CameraRecording` + `GyroRecorder`
- `CameraRecording`: wraps an `cv2.VideoWriter`. Timestamped filename. Started lazily on first frame so frame dimensions are known; `start()` accepts `is_colour` to configure the VideoWriter correctly for both colour and mono cameras. Writes each frame via `write()`. `stop()` releases the writer.
- `GyroRecorder`: writes gyro readings to a `.jsonl` file. Filename timestamp is synced to the primary camera's recording timestamp so both files can be aligned in post-processing.

### `camera/camera_tracking.py` — `CameraTracking`
Stateless. Single method `draw_detections(frame, results, estimates=None)`:
- Calls `results.plot()` to generate an annotated frame with YOLO bounding boxes and track IDs.
- If `estimates` is provided and non-empty, iterates over each `DetectionEstimate` and overlays a distance label using `cv2.putText()`. Label format: `"{distance_m:.1f}m"`. Rendered as white text with a black drop-shadow outline for contrast. Positioned inside the top-right corner of each bounding box. Detections with `distance_m = None` (low confidence) are skipped.
- `_frame` is accepted for API compatibility only; the annotated output comes from YOLO's `results.plot()`.

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
- Returns a `list[DetectionEstimate]` (TypedDict) — one entry per detection.
- Main method: `estimate(depth_frame, results, image_width) -> list[DetectionEstimate]`
- **Distance:** crops the inner 40% of each bounding box (30% edge crop on each side, via `_EDGE_CROP = 0.3`). Filters invalid pixels (`< 1mm` or `> 10,000mm`). Takes `np.median` of valid pixels and converts to metres. If fewer than 10 valid pixels remain, `distance_m` is set to `None` to signal low confidence.
- **Bearing:** normalised horizontal offset — `(box_centre_x - image_width / 2) / (image_width / 2)`. Range is [-1.0, +1.0]: negative = left of centre, positive = right of centre, 0 = dead ahead.
- Returns `DetectionEstimate` TypedDict per detection with keys: `track_id`, `confidence`, `distance_m`, `bearing_normalised`, `bbox_xyxy`.
- Constants: `_MIN_DEPTH_MM = 1`, `_MAX_DEPTH_MM = 10_000`, `_MIN_VALID_PIXELS = 10`, `_EDGE_CROP = 0.3`.

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
  ├── CAM_A (colour, 1920×1080) ──→ video queue ──→ get_frame("CAM_A") ──→ [warp if CMC] ──→ YOLO inference ──┐
  │                                                                                                             ├──→ draw_detections(estimates) ──→ annotated frame ──→ record + display
  ├── CAM_B + CAM_C ──→ StereoDepth node ──→ depth queue ──→ get_depth_frame() ──→ [same warp if CMC] ──→ TargetEstimator.estimate() ──┘
  │
  ├── CAM_B (mono,  640×400)   ──→ video queue ──→ get_frame("CAM_B") ──→ (no inference) ──→ record only (not displayed)
  ├── CAM_C (mono,  640×400)   ──→ video queue ──→ get_frame("CAM_C") ──→ (no inference) ──→ record only (not displayed)
  └── IMU (GYROSCOPE_RAW 100Hz, always active) ──→ imu queue ──→ get_gyro_data()
        ├──→ JSONL recording (if record_gyroscope=True)
        └──→ ImuIntegrator.update() ──→ get_warp_and_reset() → warp matrix (or None if motion < 0.5 px)
```

---

## What YOLO Returns

`results.boxes` contains per-detection:
- Bounding box (xyxy pixel coords in the colour frame)
- Confidence score
- Class ID
- Track ID (when `persist=True`)

Only the colour frame (CAM_A) goes through YOLO. The depth frame is fetched separately and associated with detections inside `_apply_inference()` via `TargetEstimator`.

---

## Output Files

Saved to `output/recordings/`, timestamped per session (`YYYYMMDD_HHMMSS`). All files in a session share the same timestamp, set at `Pipeline.__init__` time:
- `cam_a_recording_<timestamp>.mp4` — colour camera video
- `cam_b_recording_<timestamp>.mp4` — left mono video
- `cam_c_recording_<timestamp>.mp4` — right mono video
- `recording_<timestamp>.jsonl` — IMU gyro readings `{timestamp_s, x, y, z}` per line

---

## Key Design Decisions

- **Dynamic camera discovery:** cameras are not hardcoded. The pipeline queries the device at runtime for connected sockets and their capabilities. This means the pipeline adapts if the hardware changes.
- **Lazy recorder init:** recorders are opened on the first frame so that frame dimensions do not need to be hardcoded.
- **Session timestamp at init:** `_session_timestamp` is generated once at `Pipeline.__init__` and shared across all recorders (video + gyro), ensuring all output files for a session have the same timestamp.
- **Gyro timestamp sync:** the JSONL gyro file shares its timestamp with the primary camera's video file, enabling post-processing alignment.
- **IMU always active:** the IMU node is always wired in the DepthAI pipeline. `record_gyroscope` only controls whether readings are written to disk. `_poll_gyro()` skips the queue drain entirely when both gyro recording and CMC are disabled.
- **CMC depth alignment:** when `imu_cmc_enabled` is True, the same affine warp applied to the RGB frame is also applied to the depth frame (using `INTER_NEAREST` to preserve raw millimetre values). This ensures bounding boxes from YOLO and depth samples from `TargetEstimator` always share the same coordinate space.
- **Trivial warp guard:** `ImuIntegrator.get_warp_and_reset()` returns `None` when the accumulated displacement is below 0.5 px in both axes, allowing the caller to skip `cv2.warpAffine` entirely on frames with negligible camera motion.
- **Depth always fetched when available:** `_apply_inference()` always attempts to fetch a depth frame. If one is not ready (no stereo node, or frame not yet in queue), `estimates` falls back to an empty list and no distance labels are drawn.
- **Stateless tracker and estimator:** `CameraTracking` and `TargetEstimator` hold no frame-to-frame state. YOLO maintains its own internal track state when `persist=True`.
- **Inference is optional:** `inference_enabled: False` in config skips YOLO, depth estimation, and distance overlay entirely. The pipeline runs as a plain recorder.

---

## Planned Next Steps

### Completed
- ~~**Restrict live view to colour camera only:**~~ Done. `_process_frame()` in `pipeline.py` gates both `_apply_inference()` and `cv2.imshow()` on `cam_name in self._colour_camera_names`. The set is populated once from hardware metadata (`get_colour_camera_names()`) immediately after `camera.start()`. Mono cameras (CAM_B, CAM_C) continue to be recorded to disk but are never passed to inference or displayed.
- ~~**Integrate `TargetEstimator` into `pipeline.py`:**~~ Done. `_apply_inference()` calls `self._camera.get_depth_frame()` and passes the result to `TargetEstimator.estimate()`. The returned estimates list is passed to `CameraTracking.draw_detections()`.
- ~~**Overlay distance on live view:**~~ Done. `CameraTracking.draw_detections()` accepts `estimates: list[DetectionEstimate] | None` and draws `"{distance_m:.1f}m"` labels with a white fill and black outline using `cv2.putText()`.

Future modules planned for `depth_perception/`:
- `fusion.py` — IMU + depth fusion helpers (Phase 4)
