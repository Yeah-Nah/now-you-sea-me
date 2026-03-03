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
        self._recorders: dict[str, CameraRecording] | None = (
            {
                cam: CameraRecording(
                    output_dir=settings.output_dir,
                    file_prefix=f"{cam}_recording",
                )
                for cam in ["cam_a", "cam_b", "cam_c"]
            }
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
        self._gyro_recorder: GyroRecorder | None = (
            GyroRecorder(output_dir=settings.output_dir)
            if settings.record_gyroscope
            else None
        )
        self._recording_started: dict[str, bool] = dict.fromkeys(
            ["cam_a", "cam_b", "cam_c"], False
        )
        self._gyro_started = False

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
            any_frame = False

            for cam_name in self._camera.get_camera_names():
                frame = self._camera.get_frame(cam_name)
                if frame is None:
                    continue

                any_frame = True

                # Lazily start each camera's recorder once we know the frame dimensions.
                if (
                    self._recorders is not None
                    and not self._recording_started[cam_name]
                ):
                    height, width = frame.shape[:2]
                    self._recorders[cam_name].start(
                        frame_width=width, frame_height=height, fps=30
                    )
                    self._recording_started[cam_name] = True

                # Start gyro recorder once cam_a is recording, sharing its timestamp.
                if (
                    self._gyro_recorder is not None
                    and not self._gyro_started
                    and cam_name == "cam_a"
                ):
                    ts = (
                        self._recorders["cam_a"].timestamp
                        if self._recorders is not None
                        else None
                    )
                    self._gyro_recorder.start(timestamp=ts)
                    self._gyro_started = True

                display_frame = frame

                if self._detector is not None:
                    results = self._detector.run(frame)
                    if results is not None and self._tracker is not None:
                        display_frame = self._tracker.draw_detections(frame, results)

                if self._recorders is not None:
                    self._recorders[cam_name].write(display_frame)

                if self._settings.live_view_enabled:
                    cv2.imshow(f"OAK-D Feed - {cam_name.upper()}", display_frame)

            if self._gyro_recorder is not None and self._gyro_started:
                readings = self._camera.get_gyro_data()
                if readings:
                    self._gyro_recorder.write(readings)

            if not any_frame:
                time.sleep(0.001)  # 1ms pause to avoid busy-waiting
                continue

            if self._settings.live_view_enabled and cv2.waitKey(1) == ord("q"):
                logger.info("'q' pressed — stopping pipeline.")
                break

    def _shutdown(self) -> None:
        """Stop recording, release camera, and destroy display windows."""
        if self._recorders is not None:
            for recorder in self._recorders.values():
                recorder.stop()
        if self._gyro_recorder is not None:
            self._gyro_recorder.stop()
        self._camera.stop()
        cv2.destroyAllWindows()
        logger.info("Pipeline shut down cleanly.")
