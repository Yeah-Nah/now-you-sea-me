"""Pipeline orchestration for oakd-camera-tracking system.

This module coordinates the camera feed, YOLO model inference, and tracking
components to detect and track boats in video footage.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import cv2
from camera.camera_access import CameraAccess
from camera.camera_recording import CameraRecording
from camera.camera_tracking import CameraTracking
from inference.object_detection import ObjectDetection
from loguru import logger

if TYPE_CHECKING:
    from settings import Settings


class Pipeline:
    """Orchestrates camera access, inference, tracking, and recording.

    Parameters
    ----------
    settings : Settings
        Fully resolved and validated settings instance.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._camera = CameraAccess(record_gyroscope=settings.record_gyroscope)
        self._recorder: CameraRecording | None = (
            CameraRecording(output_dir=settings.output_dir)
            if settings.recording_enabled
            else None
        )
        self._tracker: CameraTracking | None = (
            CameraTracking() if settings.inference_enabled else None
        )
        self._detector: ObjectDetection | None = (
            ObjectDetection(
                model_path=settings.model_path,
                model_config=settings.model_config,
            )
            if settings.inference_enabled
            else None
        )
        self._recording_started = False

    def run(self) -> None:
        """Start the pipeline and enter the main processing loop.

        Connects to the camera, begins optional recording, and processes
        frames until 'q' is pressed or the pipeline is interrupted.
        """
        logger.info("Starting pipeline...")
        try:
            self._camera.start()
        except RuntimeError:
            logger.error("Aborting pipeline: camera unavailable.")
            sys.exit(1)

        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user.")
        finally:
            self._shutdown()

    def _main_loop(self) -> None:
        while True:
            frame = self._camera.get_frame()
            if frame is None:
                continue

            # Lazily start the recorder once we know the actual frame dimensions.
            if self._recorder is not None and not self._recording_started:
                height, width = frame.shape[:2]
                self._recorder.start(frame_width=width, frame_height=height, fps=30)
                self._recording_started = True

            display_frame = frame

            if self._detector is not None:
                results = self._detector.run(frame)
                if results is not None and self._tracker is not None:
                    display_frame = self._tracker.draw_detections(frame, results)

            if self._recorder is not None:
                self._recorder.write(display_frame)

            if self._settings.record_gyroscope:
                gyro = self._camera.get_gyro_data()
                if gyro is not None:
                    logger.debug(f"Gyro data: {gyro}")

            if self._settings.live_view_enabled:
                cv2.imshow("OAK-D Feed", display_frame)
                if cv2.waitKey(1) == ord("q"):
                    logger.info("'q' pressed — stopping pipeline.")
                    break

    def _shutdown(self) -> None:
        """Stop recording, release camera, and destroy display windows."""
        if self._recorder is not None:
            self._recorder.stop()
        self._camera.stop()
        cv2.destroyAllWindows()
        logger.info("Pipeline shut down cleanly.")
