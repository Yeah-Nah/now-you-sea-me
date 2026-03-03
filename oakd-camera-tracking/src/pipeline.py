"""Pipeline orchestration for oakd-camera-tracking system.

This module coordinates the camera feed, YOLO model inference, and tracking
components to detect and track boats in video footage.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

import cv2
from loguru import logger

from .camera.camera_access import CameraAccess
from .camera.camera_recording import CameraRecording, GyroRecorder
from .camera.camera_tracking import CameraTracking
from .inference.object_detection import ObjectDetection

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray
    from settings import Settings

_FPS: int = 30
_IDLE_SLEEP_S: float = 0.001
_QUIT_KEY: int = ord("q")


class Pipeline:
    """Orchestrates camera access, inference, tracking, and recording.

    Parameters
    ----------
    settings : Settings
        Fully resolved and validated settings instance.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._camera = self._create_camera()
        self._tracker = self._create_tracker()
        self._detector = self._create_detector()
        self._gyro_recorder = self._create_gyro_recorder()
        # Populated in _setup_recorders() after camera connects so that
        # names are sourced from the device rather than hardcoded here.
        self._recorders: dict[str, CameraRecording] = {}
        self._recording_started: dict[str, bool] = {}
        self._gyro_started: bool = False

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def live_view_enabled(self) -> bool:
        """Whether to display each camera feed in a live window."""
        return self._settings.live_view_enabled

    @property
    def recording_enabled(self) -> bool:
        """Whether to record each camera feed to disk."""
        return self._settings.recording_enabled

    @property
    def _primary_camera(self) -> str:
        """Name of the first camera reported by the device.

        The gyro recorder syncs its filename timestamp to this camera's
        recording so that video and IMU data can be aligned in post.
        """
        names = self._camera.get_camera_names()
        return names[0] if names else ""

    # ------------------------------------------------------------------ #
    # Factory methods                                                      #
    # ------------------------------------------------------------------ #

    def _create_camera(self) -> CameraAccess:
        """Instantiate the camera access object."""
        return CameraAccess(record_gyroscope=self._settings.record_gyroscope)

    def _create_tracker(self) -> CameraTracking | None:
        """Create a tracker instance if inference is enabled."""
        return CameraTracking() if self._settings.inference_enabled else None

    def _create_detector(self) -> ObjectDetection | None:
        """Create an object detector if inference is enabled."""
        if not self._settings.inference_enabled:
            return None
        return ObjectDetection(
            model_path=self._settings.model_path,
            model_config=self._settings.model_config,
        )

    def _create_gyro_recorder(self) -> GyroRecorder | None:
        """Create a gyroscope recorder if gyro recording is enabled."""
        if not self._settings.record_gyroscope:
            return None
        return GyroRecorder(output_dir=self._settings.output_dir)

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Start the pipeline and enter the main processing loop.

        Connects to the camera, sets up recorders based on the device's
        reported camera list, then processes frames until 'q' is pressed
        or the pipeline is interrupted.
        """
        logger.info("Starting pipeline...")
        try:
            self._camera.start()
        except RuntimeError:
            logger.error("Aborting pipeline: camera unavailable.")
            sys.exit(1)

        self._setup_recorders()

        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user.")
        finally:
            self._shutdown()

    # ------------------------------------------------------------------ #
    # Setup                                                                #
    # ------------------------------------------------------------------ #

    def _setup_recorders(self) -> None:
        """Create one video recorder per camera using names from the connected device."""
        if not self.recording_enabled:
            return
        for cam_name in self._camera.get_camera_names():
            self._recorders[cam_name] = CameraRecording(
                output_dir=self._settings.output_dir,
                file_prefix=f"{cam_name}_recording",
            )
            self._recording_started[cam_name] = False

    # ------------------------------------------------------------------ #
    # Main loop                                                            #
    # ------------------------------------------------------------------ #

    def _main_loop(self) -> None:
        while True:
            any_frame = False

            for cam_name in self._camera.get_camera_names():
                frame = self._camera.get_frame(cam_name)
                if frame is not None:
                    self._process_frame(cam_name, frame)
                    any_frame = True

            self._poll_gyro()

            if not any_frame:
                time.sleep(_IDLE_SLEEP_S)
                continue

            if self.live_view_enabled and cv2.waitKey(1) == _QUIT_KEY:
                logger.info("'q' pressed — stopping pipeline.")
                break

    # ------------------------------------------------------------------ #
    # Per-frame processing                                                 #
    # ------------------------------------------------------------------ #

    def _process_frame(self, cam_name: str, frame: NDArray[np.uint8]) -> None:
        """Record, annotate, and optionally display one frame from a single camera.

        Parameters
        ----------
        cam_name : str
            Camera identifier (e.g. ``"cam_a"``).
        frame : NDArray[np.uint8]
            Raw BGR frame from the camera.
        """
        self._lazy_start_recorder(cam_name, frame)
        self._lazy_start_gyro(cam_name)

        display_frame = self._apply_inference(frame)

        if cam_name in self._recorders:
            self._recorders[cam_name].write(display_frame)

        if self.live_view_enabled:
            cv2.imshow(f"OAK-D Feed - {cam_name.upper()}", display_frame)

    def _apply_inference(self, frame: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Run object detection and draw annotations if inference is enabled.

        Parameters
        ----------
        frame : NDArray[np.uint8]
            Raw BGR frame.

        Returns
        -------
        NDArray[np.uint8]
            Annotated frame, or the original frame if inference is disabled.
        """
        if self._detector is None:
            return frame
        results = self._detector.run(frame)
        if results is not None and self._tracker is not None:
            return self._tracker.draw_detections(frame, results)
        return frame

    def _poll_gyro(self) -> None:
        """Drain the IMU queue and flush any new readings to disk."""
        if self._gyro_recorder is None or not self._gyro_started:
            return
        readings = self._camera.get_gyro_data()
        if readings:
            self._gyro_recorder.write(readings)

    # ------------------------------------------------------------------ #
    # Lazy initialisation                                                  #
    # ------------------------------------------------------------------ #

    def _lazy_start_recorder(self, cam_name: str, frame: NDArray[np.uint8]) -> None:
        """Open a camera's VideoWriter on its first frame.

        OpenCV requires frame dimensions to open the writer, so initialisation
        is deferred until the first frame arrives.

        Parameters
        ----------
        cam_name : str
            Camera identifier.
        frame : NDArray[np.uint8]
            First frame received from this camera.
        """
        if self._recording_started.get(cam_name):
            return
        recorder = self._recorders.get(cam_name)
        if recorder is None:
            return
        height, width = frame.shape[:2]
        recorder.start(frame_width=width, frame_height=height, fps=_FPS)
        self._recording_started[cam_name] = True

    def _lazy_start_gyro(self, cam_name: str) -> None:
        """Start the gyro recorder when the primary camera's recorder is ready.

        Syncs the JSONL filename timestamp to the primary camera's video
        recording so that the two files can be aligned in post-processing.

        Parameters
        ----------
        cam_name : str
            Camera currently being processed.
        """
        if (
            self._gyro_recorder is None
            or self._gyro_started
            or cam_name != self._primary_camera
        ):
            return
        primary_recorder = self._recorders.get(self._primary_camera)
        ts = primary_recorder.timestamp if primary_recorder is not None else None
        self._gyro_recorder.start(timestamp=ts)
        self._gyro_started = True

    # ------------------------------------------------------------------ #
    # Shutdown                                                             #
    # ------------------------------------------------------------------ #

    def _shutdown(self) -> None:
        """Stop recording, release the camera, and destroy display windows."""
        for recorder in self._recorders.values():
            recorder.stop()
        if self._gyro_recorder is not None:
            self._gyro_recorder.stop()
        self._camera.stop()
        cv2.destroyAllWindows()
        logger.info("Pipeline shut down cleanly.")
