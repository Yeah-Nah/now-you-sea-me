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
        self._device: dai.Device | None = None
        self._video_queue: dai.DataOutputQueue | None = None
        self._imu_queue: dai.DataOutputQueue | None = None

    def start(self) -> None:
        """Build the DepthAI pipeline and open the device connection.

        Raises
        ------
        RuntimeError
            If no OAK-D device is found or the connection fails.
        """
        pipeline = self._build_pipeline()
        try:
            self._device = dai.Device(pipeline)
        except RuntimeError as exc:
            logger.error(f"Failed to connect to OAK-D camera: {exc}")
            raise RuntimeError(f"OAK-D camera not found or unavailable: {exc}") from exc
        self._video_queue = self._device.getOutputQueue(
            name="video", maxSize=4, blocking=False
        )
        if self._record_gyroscope:
            self._imu_queue = self._device.getOutputQueue(
                name="imu", maxSize=50, blocking=False
            )
        logger.info("OAK-D camera started successfully.")

    def _build_pipeline(self) -> dai.Pipeline:
        pipeline = dai.Pipeline()

        cam: dai.node.ColorCamera = pipeline.create(dai.node.ColorCamera)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setFps(self._fps)

        xout: dai.node.XLinkOut = pipeline.create(dai.node.XLinkOut)
        xout.setStreamName("video")
        cam.video.link(xout.input)

        if self._record_gyroscope:
            imu: dai.node.IMU = pipeline.create(dai.node.IMU)
            imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_CALIBRATED, 100)
            imu_xout: dai.node.XLinkOut = pipeline.create(dai.node.XLinkOut)
            imu_xout.setStreamName("imu")
            imu.out.link(imu_xout.input)

        return pipeline

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

    def get_gyro_data(self) -> dai.IMUData | None:
        """Return the latest IMU packet, or None if gyroscope is not enabled.

        Returns
        -------
        dai.IMUData | None
            Latest IMU data packet, or None.
        """
        if self._imu_queue is None:
            return None
        return self._imu_queue.tryGet()

    def stop(self) -> None:
        """Close the device connection and release resources."""
        if self._device is not None:
            self._device.close()
            self._device = None
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
