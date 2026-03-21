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

    Camera sockets and their native resolutions are discovered at runtime
    from the connected device, so no static socket configuration is needed.

    Parameters
    ----------
    fps : int
        Target frames per second for each colourCamera node.
    """

    def __init__(
        self,
        fps: int = 30,
        colour_resolution: tuple[int, int] = (1920, 1080),
        mono_resolution: tuple[int, int] = (640, 400),
    ) -> None:
        self._fps = fps
        self._colour_resolution = colour_resolution
        self._mono_resolution = mono_resolution
        self._pipeline: dai.Pipeline | None = None
        self._video_queues: dict[str, dai.DataOutputQueue] = {}
        self._imu_queue: dai.DataOutputQueue | None = None
        self._depth_queue: dai.DataOutputQueue | None = None
        self._camera_features: list[dai.CameraFeatures] = []

    def start(self) -> None:
        """Discover cameras, build the DepthAI pipeline, and open the device connection.

        Camera sockets and native resolutions are queried from the device
        before the pipeline is constructed, so the pipeline is fully driven
        by what the hardware reports.

        Raises
        ------
        RuntimeError
            If no OAK-D device is found, or if pipeline creation fails.
        """
        try:
            self._camera_features = self._discover_cameras()
            self._pipeline = dai.Pipeline()
            self._build_pipeline()
            self._pipeline.start()
        except RuntimeError as exc:
            logger.error(f"Failed to connect to OAK-D camera: {exc}")
            self._pipeline = None
            raise RuntimeError(f"OAK-D camera not found or unavailable: {exc}") from exc
        except Exception as exc:
            logger.error(f"Unexpected error during pipeline initialization: {exc}")
            self._pipeline = None
            raise RuntimeError(f"Pipeline initialization failed: {exc}") from exc

        logger.info(
            f"OAK-D camera started with {len(self._camera_features)} sensor(s): "
            f"{self.get_camera_names()}"
        )

    def _discover_cameras(self) -> list[dai.CameraFeatures]:
        """Open a temporary device connection to query available camera sensors.

        The device is closed immediately after the query so that the pipeline
        can connect to it during ``start()``.

        Returns
        -------
        list[dai.CameraFeatures]
            Camera features for each connected sensor, including socket,
            native resolution, and sensor type, in device-reported order.

        Raises
        ------
        RuntimeError
            If no OAK-D device is detected, or if no cameras are reported.
        """
        available = dai.Device.getAllAvailableDevices()
        if not available:
            raise RuntimeError("No OAK-D device found")

        with dai.Device(available[0]) as device:
            features = list(device.getConnectedCameraFeatures())

        if not features:
            raise RuntimeError("Connected device reported no camera sensors")

        logger.debug(
            f"Discovered {len(features)} camera sensor(s) on device "
            f"'{available[0].name}'."
        )
        return features

    def _is_colour_sensor(self, cam_features: dai.CameraFeatures) -> bool:
        """Return True if *cam_features* describes a colour (RGB) sensor."""
        return any(t == dai.CameraSensorType.COLOR for t in cam_features.supportedTypes)

    def _build_pipeline(self) -> None:
        """Build all pipeline nodes: cameras, stereo depth, and IMU."""
        if self._pipeline is None:
            raise RuntimeError("Pipeline not initialized")
        mono_cameras, colour_socket = self._build_camera_nodes()
        self._build_stereo_node(mono_cameras, colour_socket)
        self._build_imu_node()

    def _build_camera_nodes(
        self,
    ) -> tuple[list[tuple[str, object]], dai.CameraBoardSocket | None]:
        """Create one Camera node per discovered sensor and populate video queues.

        Returns
        -------
        tuple[list[tuple[str, object]], dai.CameraBoardSocket | None]
            Mono camera outputs in device-reported order (each entry is
            ``(cam_name, output)``), and the socket of the first colour
            camera found (or None if no colour camera is present).
        """
        assert self._pipeline is not None
        mono_outputs: list[tuple[str, object]] = []
        colour_socket: dai.CameraBoardSocket | None = None

        for cam_features in self._camera_features:
            cam_name = cam_features.socket.name
            is_colour = self._is_colour_sensor(cam_features)
            resolution = self._colour_resolution if is_colour else self._mono_resolution
            cam = self._pipeline.create(dai.node.Camera).build(cam_features.socket)
            output = cam.requestOutput(resolution, fps=self._fps)
            self._video_queues[cam_name] = output.createOutputQueue(
                maxSize=16, blocking=False
            )
            if is_colour and colour_socket is None:
                colour_socket = cam_features.socket
            else:
                mono_outputs.append((cam_name, output))
            logger.debug(
                f"Pipeline: added '{cam_name}' ({cam_features.sensorName}) "
                f"at {resolution[0]}x{resolution[1]}."
            )

        return mono_outputs, colour_socket

    def _build_stereo_node(
        self,
        mono_outputs: list[tuple[str, object]],
        colour_socket: dai.CameraBoardSocket | None,
    ) -> None:
        """Wire a StereoDepth node if at least two mono cameras and a colour camera exist.

        Parameters
        ----------
        mono_outputs : list[tuple[str, object]]
            Mono camera outputs in device-reported order. The first two entries
            are used as the left and right stereo inputs respectively.
        colour_socket : dai.CameraBoardSocket | None
            Socket of the colour camera to align the depth map to, or None if
            no colour camera was found (stereo node will not be created).
        """
        if len(mono_outputs) < 2 or colour_socket is None:
            return
        assert self._pipeline is not None
        left_name, left_output = mono_outputs[0]
        right_name, right_output = mono_outputs[1]
        stereo = self._pipeline.create(dai.node.StereoDepth)
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        stereo.setDepthAlign(colour_socket)
        stereo.setOutputSize(*self._colour_resolution)
        left_output.link(stereo.left)  # type: ignore[attr-defined]
        right_output.link(stereo.right)  # type: ignore[attr-defined]
        self._depth_queue = stereo.depth.createOutputQueue(maxSize=8, blocking=False)
        logger.debug(
            f"Pipeline: StereoDepth node wired ({left_name}→left, "
            f"{right_name}→right, aligned to {colour_socket.name})."
        )

    def _build_imu_node(self) -> None:
        """Create and configure the IMU node. Always active regardless of recording settings."""
        assert self._pipeline is not None
        imu = self._pipeline.create(dai.node.IMU)
        imu.enableIMUSensor([dai.IMUSensor.GYROSCOPE_RAW], 100)
        imu.setBatchReportThreshold(1)
        imu.setMaxBatchReports(10)
        self._imu_queue = imu.out.createOutputQueue(maxSize=50, blocking=False)

    def get_camera_names(self) -> list[str]:
        """Return the socket names of all discovered cameras.

        Names match the ``dai.CameraBoardSocket`` enum (e.g. ``"CAM_A"``)
        and are only populated after ``start()`` is called.

        Returns
        -------
        list[str]
            Camera names in device-reported order.
        """
        return [f.socket.name for f in self._camera_features]

    def get_colour_camera_names(self) -> set[str]:
        """Return socket names of all colour (RGB) cameras.

        Derived from hardware metadata; only populated after ``start()``.

        Returns
        -------
        set[str]
            Socket names of colour cameras (e.g. ``{"CAM_A"}``).
        """
        return {
            f.socket.name for f in self._camera_features if self._is_colour_sensor(f)
        }

    def is_colour_camera(self, frame: NDArray[np.uint8]) -> bool:
        """Determine if a given frame is from a colour camera based on its shape.

        Colour camera frames have 3 channels (H, W, 3), while mono cameras
        have a single channel (H, W).

        Parameters
        ----------
        frame : NDArray[np.uint8]
            Frame array to check.

        Returns
        -------
        bool
            True if the frame has 3 channels and is likely from a colour camera.
        """
        return frame.ndim == 3 and frame.shape[2] == 3

    def get_frame(self, cam_name: str) -> NDArray[np.uint8] | None:
        """Retrieve the most recent frame from a camera's queue.

        Parameters
        ----------
        cam_name : str
            Name of the camera (e.g. ``"CAM_A"``).

        Returns
        -------
        NDArray[np.uint8] | None
            BGR or grayscale frame, or None if no frame is ready.
        """
        queue = self._video_queues.get(cam_name)
        if queue is None:
            return None
        if not queue.has():
            return None
        msg = queue.get()

        return msg.getCvFrame()  # type: ignore[no-any-return]

    def get_depth_frame(self) -> NDArray[np.uint16] | None:
        """Return the most recent stereo depth frame, or None if not ready.

        Depth pixel values are distances in millimetres encoded as uint16.
        Returns None if the StereoDepth node was not wired (e.g. only one
        mono camera present) or if no frame is available yet.

        Returns
        -------
        NDArray[np.uint16] | None
            Depth frame aligned to CAM_A, or None.
        """
        if self._depth_queue is None or not self._depth_queue.has():
            return None
        return self._depth_queue.get().getCvFrame()  # type: ignore[no-any-return]

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

        # Clear all instance state to prevent use-after-stop
        self._video_queues.clear()
        self._imu_queue = None
        self._depth_queue = None
        self._camera_features.clear()

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
