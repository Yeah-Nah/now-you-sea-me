"""Detection overlay drawing for tracked camera frames."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from ultralytics.engine.results import Results


class CameraTracking:
    """Applies inference results and draws bounding boxes on camera frames.

    This class is stateless. A single instance can be reused across frames.
    """

    def draw_detections(
        self,
        frame: NDArray[np.uint8],
        results: Results,
    ) -> NDArray[np.uint8]:
        """Draw bounding boxes and track IDs from YOLO results onto a frame.

        Parameters
        ----------
        frame : NDArray[np.uint8]
            Original BGR frame (unused directly; present for API clarity).
        results : Results
            YOLO Results object returned by model.track() or model.predict().

        Returns
        -------
        NDArray[np.uint8]
            Annotated BGR frame with boxes and track IDs drawn.
        """
        annotated: NDArray[np.uint8] = results.plot()
        n = len(results.boxes) if results.boxes is not None else 0
        logger.debug(f"Drew {n} detection(s) on frame.")
        return annotated
