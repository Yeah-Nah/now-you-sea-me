"""OAK-D camera access via DepthAI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import depthai as dai
import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from numpy.typing import NDArray


class CameraAccess:
    """Handles OAK-D camera connection and frame access using DepthAI.

    Parameters
    ----------
    record_gyroscope : bool
        If True, enables the IMU node and exposes gyroscope readings.
    fps : int
        Target frames per second for the ColorCamera node.
    """

    def __init__(self, record_gyroscope: bool, fps: int = 30) -> None:
        self._record_gyroscope = record_gyroscope
        self._fps = fps
        self._pipeline: dai.Pipeline | None = None
        self._video_queue: dai.DataOutputQueue | None = None
        self._imu_queue: dai.DataOutputQueue | None = None

    def start(self) -> None:
        """Build the DepthAI pipeline and open the device connection.

        Raises
        ------
        RuntimeError
            If pipeline creation fails or no OAK-D device is found.
        """
        try:
            self._pipeline = dai.Pipeline()
            self._build_pipeline()
            self._pipeline.start()
        except RuntimeError as exc:
            logger.error(f"Failed to connect to OAK-D camera: {exc}")
            self._pipeline = None  # Ensure cleanup on failure
            raise RuntimeError(f"OAK-D camera not found or unavailable: {exc}") from exc
        except Exception as exc:
            logger.error(f"Unexpected error during pipeline initialization: {exc}")
            self._pipeline = None
            raise RuntimeError(f"Pipeline initialization failed: {exc}") from exc

        logger.info("OAK-D camera started successfully.")

    def _build_pipeline(self) -> None:
        """Build the DepthAI pipeline nodes and output queues using V3 API."""
        if self._pipeline is None:
            raise RuntimeError("Pipeline not initialized")

        cam = self._pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        self._video_queue = cam.requestOutput(
            (1280, 720), fps=self._fps
        ).createOutputQueue(maxSize=16, blocking=False)

        if self._record_gyroscope:
            imu = self._pipeline.create(dai.node.IMU)
            imu.enableIMUSensor([dai.IMUSensor.GYROSCOPE_RAW], 100)
            imu.setBatchReportThreshold(1)
            imu.setMaxBatchReports(10)
            self._imu_queue = imu.out.createOutputQueue(maxSize=50, blocking=False)

    def get_frame(self) -> NDArray[np.uint8] | None:
        """Pop the latest frame from the video queue.

        Returns
        -------
        NDArray[np.uint8] | None
            BGR numpy array of shape (H, W, 3), or None if no frame is available.
        """
        if self._video_queue is None:
            return None
        packet = self._video_queue.tryGet()
        if packet is None:
            return None
        frame: NDArray[np.uint8] = packet.getCvFrame()
        return frame

    def get_gyro_data(self) -> list[dict[str, float]] | None:
        """Return parsed gyroscope readings from the latest IMU packet.

        Returns
        -------
        list[dict[str, float]] | None
            List of readings with keys ``timestamp_s``, ``x``, ``y``, ``z``,
            or None if no packet is available or gyroscope is not enabled.
        """
        if self._imu_queue is None:
            return None
        packet = self._imu_queue.tryGet()
        if packet is None:
            return None
        readings = []
        for imu_packet in packet.packets:
            gyro = imu_packet.gyroscope
            readings.append(
                {
                    "timestamp_s": gyro.getTimestamp().total_seconds(),
                    "x": gyro.x,
                    "y": gyro.y,
                    "z": gyro.z,
                }
            )
        return readings or None

    def stop(self) -> None:
        """Stop the pipeline and release resources."""
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None
            logger.info("OAK-D camera stopped.")

    def __enter__(self) -> CameraAccess:
        """Start the camera on context entry."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Stop the camera on context exit."""
        self.stop()
