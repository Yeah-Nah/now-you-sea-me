"""3D target position estimation from YOLO detections and a stereo depth frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from ultralytics.engine.results import Results

# Depth sanity limits (millimetres)
_MIN_DEPTH_MM: int = 1
_MAX_DEPTH_MM: int = 10_000
_MIN_VALID_PIXELS: int = 10

# Fraction of the bounding box to crop from each edge before sampling depth.
# 0.4 means the inner 20% of width and height is sampled.
_EDGE_CROP: float = 0.4


class TargetEstimator:
    """Estimates distance and bearing for each detected target.

    Combines a stereo depth frame (aligned to the colour camera) with YOLO
    detection results to produce per-target 3D position estimates.

    This class is stateless — a single instance can be reused across frames.
    """

    def estimate(
        self,
        depth_frame: NDArray[np.uint16],
        results: Results,
        image_width: int,
    ) -> list[dict]:
        """Estimate distance and bearing for every detection in *results*.

        Parameters
        ----------
        depth_frame : NDArray[np.uint16]
            Depth map aligned to the colour camera frame. Pixel values are
            distances in millimetres (uint16). Zero indicates an invalid pixel.
        results : Results
            YOLO Results object from ``model.track()`` or ``model.predict()``.
        image_width : int
            Width of the colour camera frame in pixels. Used to compute the
            normalised bearing.

        Returns
        -------
        list[dict]
            One dict per detection with keys:
            ``track_id``, ``confidence``, ``distance_m``,
            ``bearing_normalised``, ``bbox_xyxy``.
        """
        estimates: list[dict] = []

        if results.boxes is None or len(results.boxes) == 0:
            return estimates

        frame_h, frame_w = depth_frame.shape[:2]
        half_width = image_width / 2.0

        for i, box in enumerate(results.boxes):
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # --- bearing ---
            box_centre_x = (x1 + x2) / 2.0
            bearing = (box_centre_x - half_width) / half_width

            # --- depth sampling: inner (1 - 2*_EDGE_CROP) of the box area ---
            bw = x2 - x1
            bh = y2 - y1
            sx1 = int(max(0, x1 + _EDGE_CROP * bw))
            sy1 = int(max(0, y1 + _EDGE_CROP * bh))
            sx2 = int(min(frame_w, x2 - _EDGE_CROP * bw))
            sy2 = int(min(frame_h, y2 - _EDGE_CROP * bh))

            region = depth_frame[sy1:sy2, sx1:sx2]
            valid = region[(region >= _MIN_DEPTH_MM) & (region <= _MAX_DEPTH_MM)]

            if len(valid) < _MIN_VALID_PIXELS:
                distance_m = None
            else:
                distance_m = float(np.median(valid)) / 1000.0

            # --- track ID ---
            track_id: int | None = None
            if results.boxes.id is not None:
                track_id = int(results.boxes.id[i].item())

            estimates.append(
                {
                    "track_id": track_id,
                    "confidence": float(box.conf[0].item()),
                    "distance_m": distance_m,
                    "bearing_normalised": bearing,
                    "bbox_xyxy": [x1, y1, x2, y2],
                }
            )

        return estimates
