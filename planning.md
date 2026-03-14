# UGV Rover — Object Detection & Avoidance: Phase Plan

## Project Goal

Build a self-driving robotic rover using:
- **Waveshare UGV Rover** (hardware platform)
- **Raspberry Pi** (compute)
- **OAK-D Camera** (perception — depth + RGB)
- **Custom YOLO model** (object detection)
- **ROS2** (software framework)

The rover will detect a target object, follow it autonomously, and navigate around obstacles in real time.

---

## Role Requirements Coverage

### Grad Robotics Role

| Requirement | Phase Achieved |
|---|---|
| Python programming | Already have / Phase 1 |
| Fundamental robotics concepts | Phase 1–2 |
| ROS/ROS2 experience | Phase 2 |
| Sensors and actuators | Phase 1 |
| Hardware integration | Phase 1 |
| Git / version control | Already have |
| Linux experience | Already have / Phase 1 |

### Lead ML & Robotics Engineer Role

| Requirement | Phase Achieved |
|---|---|
| ROS2 proficiency | Phase 2 |
| ONNX model export | Phase 3 |
| OpenCV / computer vision | Already have / Phase 2 |
| Real-time perception systems | Phase 2–3 |
| Sensor fusion (depth + IMU) | Phase 4 |
| Spatial transformations (TF2) | Phase 3 |
| Camera calibration | Phase 3 |

---

## Phases

---

### Phase 0 — Existing Pipeline ✅ Complete

**What's built:**
- OAK-D camera access
- YOLO inference (custom-trained boat detection model)
- Object tracking across frames
- Pipeline recording output
- Configurable via YAML (dev machine / Pi modes)

**Requirements ticked:**
- Python programming
- Computer vision with OpenCV
- Real-time perception pipeline
- Git and Linux basics

---

### Phase 1 — Hardware Integration

**Goal:** Get the Raspberry Pi physically integrated with the UGV Rover and able to send basic motor commands.

**Tasks:**
- Flash **Ubuntu 22.04** onto Raspberry Pi (required for ROS2)
- Physically mount Pi and OAK-D camera onto UGV Rover
- Install Waveshare UGV Python SDK
- Verify serial/USB communication between Pi and UGV motor controller
- Test basic manual drive commands from Pi (forward, reverse, turn)
- Port existing pipeline to run on Pi + Ubuntu

**Requirements ticked:**
- Sensors and actuators (OAK-D = sensor, motors = actuators)
- Hardware integration (Pi → UGV)
- Linux (Ubuntu on Pi)
- Fundamental robotics concepts

---

### Phase 2 — ROS2 Integration & Object Following

**Goal:** Port the pipeline into ROS2 nodes and implement basic object following using the YOLO detections and OAK-D depth data.

**Tasks:**
- Install **ROS2 Humble** on Ubuntu Pi
- Restructure pipeline into ROS2 nodes:
  - `oakd_node` — publishes RGB frames and depth maps
  - `detection_node` — runs YOLO, publishes detections
  - `tracking_node` — maintains tracked object across frames
  - `control_node` — subscribes to tracked object, publishes motor commands
- Implement object-following logic:
  - Use detection bounding box centre to steer rover left/right
  - Use OAK-D depth reading to control approach speed (stop before collision)
- Write ROS2 launch file to start full pipeline with one command
- Test object following end-to-end

**Requirements ticked:**
- ROS2 (nodes, topics, launch files)
- Real-time perception system
- Sensor integration (depth for distance control)
- Python in a structured robotics framework

---

### Phase 3 — Obstacle Avoidance & Pipeline Optimisation

**Goal:** Add obstacle avoidance using the OAK-D depth map and optimise the model for edge deployment.

**Tasks:**
- Implement depth-map-based obstacle avoidance in `control_node`:
  - Divide depth frame into zones (left, centre, right)
  - If centre zone depth is below threshold → stop or navigate around
  - Combine with object-following logic (prioritise avoidance over following)
- Export YOLO model to **ONNX** format
  - Validate ONNX model output matches PyTorch output
  - Integrate ONNX runtime into `detection_node` for faster inference
- Set up **ROS2 TF2** transforms:
  - Define camera frame → robot base frame transform
  - Publish detection positions in robot coordinate space
- Perform **OAK-D camera calibration** using OpenCV calibration tools
  - Validate intrinsic parameters
  - Feed calibrated parameters into depth pipeline

**Requirements ticked:**
- ONNX model export and deployment
- Spatial transformations and coordinate system conversions (TF2)
- Camera calibration techniques
- Obstacle avoidance behaviour

---

### Phase 4 — Sensor Fusion & Advanced Navigation

**Goal:** Improve navigation reliability by fusing multiple data sources and integrating the Nav2 stack.

**Tasks:**
- Integrate **IMU data** from UGV onboard IMU into ROS2:
  - Publish IMU data as a ROS2 topic
  - Fuse IMU + OAK-D depth for more robust obstacle detection
  - Use IMU to detect and correct for rover tipping or slip
- Integrate **Nav2 stack** for structured path planning:
  - Build a local costmap from OAK-D depth data
  - Use Nav2 local planner for reactive obstacle avoidance
  - Allow rover to navigate around obstacles and resume object following
- Add **ROS2 Bag** recording for logging sensor data during runs
  - Use bags to replay and debug navigation behaviour offline

**Requirements ticked:**
- Sensor fusion algorithms (depth + IMU)
- Advanced ROS2 (Nav2, costmaps, planners)
- Real-time multi-source perception

---

### Phase 5 — Stretch Goals

These are optional additions to further strengthen the portfolio:

| Feature | What It Demonstrates |
|---|---|
| Swap Pi for **Jetson Orin NX** | CUDA, TensorRT, GPU-accelerated inference |
| TensorRT model export | TensorRT experience (lead role requirement) |
| Multi-object tracking (follow specific target in a crowd) | Advanced tracking algorithms |
| Web dashboard for live rover telemetry | Full-stack robotics systems integration |
| Train a new YOLO model on rover-specific objects | End-to-end ML pipeline ownership |

---

## Architecture Overview

```
OAK-D Camera
    │
    ▼
[oakd_node]
  publishes: /rgb/image, /depth/image
    │
    ▼
[detection_node]  ←── Custom YOLO model (ONNX)
  publishes: /detections
    │
    ▼
[tracking_node]
  publishes: /tracked_object
    │
    ├──────────────────────────┐
    ▼                          ▼
[control_node]         [obstacle_avoidance_node]
  (object following)     (depth zone analysis)
    │                          │
    └──────────┬───────────────┘
               ▼
       /cmd_vel topic
               │
               ▼
       UGV Motor Controller
               │
               ▼
           Rover moves
```

---

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Hardware | Waveshare UGV Rover, Raspberry Pi, OAK-D |
| OS | Ubuntu 22.04 |
| Robot Framework | ROS2 Humble |
| Object Detection | YOLO (custom trained) → ONNX |
| Computer Vision | OpenCV, DepthAI SDK |
| Navigation | Nav2 stack |
| Language | Python (primary) |
| Version Control | Git |
