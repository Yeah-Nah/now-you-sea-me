## Structure and Pipeline Planning
Focusing on the camera connection with tracking and recording. Which can be developed in a way that can then be used on the Raspberry PI device when the parts arrive and development gets that far.

### Proposed Structure

#### Config Setup
`configs/model_config.yaml` - Contains settings specific to YOLO models. Determines settings for YOLO model used in pipeline.
`configs/pipeline_config.yaml` - Contains settings for pipeline. E.g. if to enable camera feed viewing, object tracking and or recording.
`src/utils/config_utils.py` - Contains functions to validate config file settings. Used in `settings.py` file.
`src/settings.py` - Pulls config file parameters and validates them with functions in the  `config_utils.py` file.

#### Edge Device Access and Recording
`src/camera/camera_access.py` - Contains the code to connect to the camera nodes and outputs the frames from the camera feed. Uses DepthAI library.
`src/camera/camera_tracking.py` - Uses the inference pipeline and draws the bounding boxes on the frames.
`src/camera/camera_recording.py` - If enabled, records the video feed from the camera and saves to an output folder. If enabled, with the predicted bounding boxes.

#### Inferencing Pipeline
`src/inference/object_detection.py` - Contains the YOLO inference pipeline to predict the bounding boxes. Uses the model named in the config file.