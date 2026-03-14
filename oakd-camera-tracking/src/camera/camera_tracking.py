"""Detection overlay drawing for tracked camera frames."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from ultralytics.engine.results import Results

    from ..depth_perception.target_estimator import DetectionEstimate


class CameraTracking:
    """Applies inference results and draws bounding boxes on camera frames.

    This class is stateless. A single instance can be reused across frames.
    """

    def draw_detections(
        self,
        _frame: NDArray[np.uint8],
        results: Results,
        estimates: list[DetectionEstimate] | None = None,
    ) -> NDArray[np.uint8]:
        """Draw bounding boxes and depth labels from YOLO results onto a frame.

        Parameters
        ----------
        _frame : NDArray[np.uint8]
            Original BGR frame, accepted for API compatibility but not used
            to generate the annotated output (which comes from results.plot()).
        results : Results
            YOLO Results object returned by model.track() or model.predict().
        estimates : list[DetectionEstimate] | None
            Per-detection depth estimates from ``TargetEstimator.estimate()``.
            Each dict must contain ``distance_m`` (float or None) and
            ``bbox_xyxy`` ([x1, y1, x2, y2]). If None or empty, only YOLO
            annotations are drawn.

        Returns
        -------
        NDArray[np.uint8]
            Annotated BGR frame with boxes, track IDs, and depth labels drawn.
        """
        annotated: NDArray[np.uint8] = results.plot()

        if estimates:
            for est in estimates:
                if est["distance_m"] is None:
                    continue
                _, y1, x2, _ = est["bbox_xyxy"]
                label = f"{est['distance_m']:.1f}m"
                origin = (int(x2) - 150, int(y1) + 80)
                # Black outline for contrast, white fill on top.
                cv2.putText(
                    annotated,
                    label,
                    origin,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    2,
                    (0, 0, 0),
                    3,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    annotated,
                    label,
                    origin,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    2,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        return annotated
