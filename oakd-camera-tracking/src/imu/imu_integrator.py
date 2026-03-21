"""IMU gyroscope integrator for camera motion compensation (CMC)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Minimum pixel displacement below which the warp is considered trivial and
# ``get_warp_and_reset()`` returns ``None`` to skip the warp step entirely.
_WARP_THRESHOLD_PX: float = 0.5


class ImuIntegrator:
    """Integrates batched gyroscope readings into a per-frame affine warp matrix.

    Accumulates yaw (z-axis) and pitch (y-axis) rotations between calls to
    ``get_warp_and_reset()``. The resulting 2×3 affine matrix can be passed
    directly to ``cv2.warpAffine`` to stabilise a frame before inference.

    Roll (x-axis) is intentionally ignored: it produces barrel distortion
    rather than translation, which a pure affine cannot correct.

    Parameters
    ----------
    focal_length_px : float
        Effective focal length of the colour camera in pixels at the
        configured output resolution. Converts rotation angles (radians)
        to pixel displacements via the small-angle approximation:
        ``Δpx = focal_length_px × θ_rad``.
    """

    def __init__(self, focal_length_px: float) -> None:
        self._focal_length_px = focal_length_px
        self._accumulated_yaw: float = 0.0
        self._accumulated_pitch: float = 0.0
        self._last_timestamp: float | None = None

    def update(self, readings: list[dict[str, float]]) -> None:
        """Accumulate gyroscope readings into the rotation state.

        Readings are expected in device-timestamp order (oldest first), as
        returned by ``CameraAccess.get_gyro_data()``. The first reading in
        each batch only advances the timestamp reference; no angle is
        accumulated for it if no prior timestamp exists.

        Parameters
        ----------
        readings : list[dict[str, float]]
            Each dict must contain keys ``timestamp_s`` (seconds, float),
            ``y`` (pitch rate, rad/s), and ``z`` (yaw rate, rad/s).
        """
        for reading in readings:
            ts = reading["timestamp_s"]
            if self._last_timestamp is not None:
                dt = ts - self._last_timestamp
                if dt > 0:
                    self._accumulated_yaw += reading["z"] * dt
                    self._accumulated_pitch += reading["y"] * dt
            self._last_timestamp = ts

    def get_warp_and_reset(self) -> NDArray[np.float32] | None:
        """Return the 2×3 affine compensation matrix and reset accumulators.

        The matrix translates image coordinates to cancel the apparent pixel
        shift caused by camera rotation since the last call:

        .. code-block:: text

            dx = -focal_length_px × Σ(ω_z · Δt)   (yaw  → horizontal shift)
            dy = -focal_length_px × Σ(ω_y · Δt)   (pitch → vertical shift)

        The negative sign inverts the camera's rotation to keep scene content
        stationary in image space.

        Returns ``None`` when the accumulated displacement is below
        ``_WARP_THRESHOLD_PX`` in both axes — i.e. when there has been no
        meaningful camera motion since the last call — so the caller can skip
        the warp entirely and avoid unnecessary CPU cost.

        Returns
        -------
        NDArray[np.float32] | None
            Shape ``(2, 3)`` affine matrix suitable for ``cv2.warpAffine()``,
            or ``None`` if the accumulated displacement is negligible.
        """
        dx = -self._focal_length_px * self._accumulated_yaw
        dy = -self._focal_length_px * self._accumulated_pitch
        self._accumulated_yaw = 0.0
        self._accumulated_pitch = 0.0
        if abs(dx) < _WARP_THRESHOLD_PX and abs(dy) < _WARP_THRESHOLD_PX:
            return None
        return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)

    def reset(self) -> None:
        """Zero all accumulated state.

        Call at pipeline startup to ensure clean state after any prior run.
        """
        self._accumulated_yaw = 0.0
        self._accumulated_pitch = 0.0
        self._last_timestamp = None
