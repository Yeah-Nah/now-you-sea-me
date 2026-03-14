"""Obstacle zone analysis from a stereo depth frame.

Placeholder for future integration with the Waveshare UGV Rover control node.
Divides the depth frame into left / centre / right zones and reports the
minimum valid depth and a simple danger classification for each zone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Depth sanity limits (millimetres)
_MIN_DEPTH_MM: int = 1
_MAX_DEPTH_MM: int = 10_000

_ZONES = ("left", "centre", "right")


class DepthZoneAnalyser:
    """Classifies obstacle danger across three horizontal depth zones.

    The depth frame is divided into equal-width left, centre, and right
    columns. For each zone the minimum valid depth is computed and compared
    against a configurable danger threshold.

    Parameters
    ----------
    danger_threshold_m : float
        Minimum depth in metres below which a zone is classified as
        ``"danger"``. Zones at or above this distance are ``"clear"``.
        Defaults to 2.0 m.
    """

    def __init__(self, danger_threshold_m: float = 2.0) -> None:
        self._danger_threshold_m = danger_threshold_m

    def analyse(
        self, depth_frame: NDArray[np.uint16]
    ) -> dict[str, dict[str, float | None | str]]:
        """Classify obstacle danger across left, centre, and right zones.

        Parameters
        ----------
        depth_frame : NDArray[np.uint16]
            Depth map aligned to the colour camera frame. Pixel values are
            distances in millimetres (uint16). Zero indicates an invalid pixel.

        Returns
        -------
        dict[str, dict[str, float | None | str]]
            Keys are ``"left"``, ``"centre"``, ``"right"``. Each value is a
            dict with:

            - ``min_depth_m`` – minimum valid depth in metres, or ``None``
              if no valid pixels are present in the zone.
            - ``status`` – ``"clear"``, ``"danger"``, or ``"unknown"``.
        """
        _, frame_w = depth_frame.shape[:2]
        third = frame_w // 3

        slices = {
            "left": depth_frame[:, :third],
            "centre": depth_frame[:, third : 2 * third],
            "right": depth_frame[:, 2 * third :],
        }

        result: dict[str, dict[str, float | str | None]] = {}
        for zone in _ZONES:
            region = slices[zone]
            valid = region[(region >= _MIN_DEPTH_MM) & (region <= _MAX_DEPTH_MM)]

            if len(valid) == 0:
                result[zone] = {"min_depth_m": None, "status": "unknown"}
            else:
                min_depth_m = float(np.min(valid)) / 1000.0
                status = "danger" if min_depth_m < self._danger_threshold_m else "clear"
                result[zone] = {"min_depth_m": min_depth_m, "status": status}

        return result
