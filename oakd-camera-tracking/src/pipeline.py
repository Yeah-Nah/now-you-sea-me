"""Pipeline orchestration for oakd-camera-tracking system.

This module coordinates the camera feed, YOLO model inference, and tracking
components to detect and track boats in video footage.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from typing import TYPE_CHECKING

import cv2
from loguru import logger

from .camera.camera_access import CameraAccess
from .camera.camera_recording import CameraRecording, GyroRecorder
from .camera.camera_tracking import CameraTracking
from .depth_perception.target_estimator import TargetEstimator
from .imu.imu_integrator import ImuIntegrator
from .inference.object_detection import ObjectDetection

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from .settings import Settings

_FPS: int = 28
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
        self._imu_integrator = self._create_imu_integrator()
        self._estimator = self._create_estimator()
        # Populated in _setup_recorders() after camera connects so that
        # names are sourced from the device rather than hardcoded here.
        self._recorders: dict[str, CameraRecording] = {}
        self._recording_started: dict[str, bool] = {}
        self._gyro_started: bool = False
        self._session_timestamp: str = self._generate_session_timestamp()
        # Populated after camera.start() from hardware metadata.
        self._colour_camera_names: set[str] = set()

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def live_view_enabled(self) -> bool:
        """Whether to display each camera feed in a live window."""
        return bool(self._settings.live_view_enabled)

    @property
    def recording_enabled(self) -> bool:
        """Whether to record each camera feed to disk."""
        return bool(self._settings.recording_enabled)

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

    def _generate_session_timestamp(self) -> str:
        """Generate a timestamp string for the current recording session."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _create_camera(self) -> CameraAccess:
        """Instantiate the camera access object."""
        return CameraAccess(
            fps=_FPS,
            colour_resolution=self._settings.colour_camera_resolution,
            mono_resolution=self._settings.mono_camera_resolution,
        )

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

    def _create_imu_integrator(self) -> ImuIntegrator | None:
        """Create an IMU integrator for camera motion compensation if enabled."""
        if not self._settings.imu_cmc_enabled:
            return None
        return ImuIntegrator(focal_length_px=self._settings.focal_length_px)

    def _create_estimator(self) -> TargetEstimator | None:
        """Create a depth estimator if inference is enabled."""
        return TargetEstimator() if self._settings.inference_enabled else None

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

        self._colour_camera_names = self._camera.get_colour_camera_names()
        if self._imu_integrator is not None:
            self._imu_integrator.reset()
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
                file_prefix=f"{cam_name.lower()}_recording",
            )
            self._recording_started[cam_name] = False

    # ------------------------------------------------------------------ #
    # Main loop                                                            #
    # ------------------------------------------------------------------ #

    def _main_loop(self) -> None:
        while True:
            any_frame = False

            self._poll_gyro()
            warp = (
                self._imu_integrator.get_warp_and_reset()
                if self._imu_integrator is not None
                else None
            )

            for cam_name in self._camera.get_camera_names():
                frame = self._camera.get_frame(cam_name)
                if frame is not None:
                    self._process_frame(cam_name, frame, warp)
                    any_frame = True

            if not any_frame:
                time.sleep(_IDLE_SLEEP_S)
                continue

            if self.live_view_enabled and cv2.waitKey(1) == _QUIT_KEY:
                logger.info("'q' pressed — stopping pipeline.")
                break

    # ------------------------------------------------------------------ #
    # Per-frame processing                                                 #
    # ------------------------------------------------------------------ #

    def _process_frame(
        self,
        cam_name: str,
        frame: NDArray[np.uint8],
        warp: NDArray[np.float32] | None,
    ) -> None:
        """Record, annotate, and optionally display one frame from a single camera.

        Parameters
        ----------
        cam_name : str
            Camera identifier (e.g. ``"CAM_A"``).
        frame : NDArray[np.uint8]
            Raw BGR frame from the camera.
        warp : NDArray[np.float32] | None
            2×3 affine compensation matrix from the IMU integrator, or None
            if camera motion compensation is disabled.
        """
        self._lazy_start_recorder(cam_name, frame)
        self._lazy_start_gyro(cam_name)

        display_frame = (
            self._apply_inference(frame, warp)
            if cam_name in self._colour_camera_names
            else frame
        )

        if cam_name in self._recorders:
            self._recorders[cam_name].write(display_frame)

        if self.live_view_enabled and cam_name in self._colour_camera_names:
            cv2.imshow(f"OAK-D Feed - {cam_name}", display_frame)

    def _apply_inference(
        self,
        frame: NDArray[np.uint8],
        warp: NDArray[np.float32] | None,
    ) -> NDArray[np.uint8]:
        """Run object detection and draw annotations if inference is enabled.

        If a CMC warp matrix is provided, the frame is stabilised with
        ``cv2.warpAffine`` before being passed to the detector, so that
        camera rotation does not corrupt the Kalman filter predictions.

        Parameters
        ----------
        frame : NDArray[np.uint8]
            Raw BGR frame.
        warp : NDArray[np.float32] | None
            2×3 affine compensation matrix, or None to skip stabilisation.

        Returns
        -------
        NDArray[np.uint8]
            Annotated frame, or the original frame if inference is disabled.
        """
        if self._detector is None:
            return frame
        if warp is not None:
            h, w = frame.shape[:2]
            frame = cv2.warpAffine(
                frame, warp, (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE,
            )
        results = self._detector.run(frame)
        if results is None or self._tracker is None:
            return frame
        depth_frame = self._camera.get_depth_frame()
        estimates = (
            self._estimator.estimate(depth_frame, results, frame.shape[1])
            if self._estimator is not None and depth_frame is not None
            else []
        )
        return self._tracker.draw_detections(frame, results, estimates)

    def _poll_gyro(self) -> None:
        """Drain the IMU queue and fan readings out to recorder and CMC integrator."""
        readings = self._camera.get_gyro_data()
        if not readings:
            return
        if self._gyro_recorder is not None and self._gyro_started:
            self._gyro_recorder.write(readings)
        if self._imu_integrator is not None:
            self._imu_integrator.update(readings)

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
        is_colour = self._camera.is_colour_camera(frame)
        recorder.start(
            frame_width=width,
            frame_height=height,
            fps=_FPS,
            is_colour=is_colour,
            timestamp=self._session_timestamp,
        )
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
        self._gyro_recorder.start(timestamp=self._session_timestamp)
        self._gyro_started = True

    # ------------------------------------------------------------------ #
    # Shutdown                                                             #
    # ------------------------------------------------------------------ #

    def _shutdown(self) -> None:
        """Stop recording, release the camera, and destroy display windows."""
        logger.info("Shutting down pipeline (please wait for camera cleanup)...")

        for recorder in self._recorders.values():
            recorder.stop()
        if self._gyro_recorder is not None:
            self._gyro_recorder.stop()

        # Camera stop can be slow on hardware; protect from repeated Ctrl+C
        try:
            self._camera.stop()
        except KeyboardInterrupt:
            logger.warning("Camera stop interrupted. Forcing cleanup...")
            # Camera will be released when Python exits anyway
        except Exception as e:
            logger.error(f"Error during camera cleanup: {e}")

        cv2.destroyAllWindows()
        logger.success("Pipeline shut down cleanly.")
