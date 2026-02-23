"""YOLO inference and tracking for object detection."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from ultralytics import YOLO

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from ultralytics.engine.results import Results


class ObjectDetection:
    """YOLO inference pipeline for object detection.

    Loads a YOLO model and exposes a single ``run()`` method for per-frame
    inference. Supports both track (persist=True) and predict modes based
    on the model config.

    Parameters
    ----------
    model_path : Path
        Absolute path to the .pt model weights file.
    model_config : dict[str, object]
        YOLO-compatible config dict. Keys must match those expected by
        YOLO: conf, classes, persist, verbose.
    """

    # Keys forwarded to model.track() / model.predict() as kwargs.
    _INFERENCE_KEYS = {"conf", "classes", "persist", "verbose"}

    def __init__(self, model_path: Path, model_config: dict[str, object]) -> None:
        self._persist = bool(model_config.get("persist", False))
        self._inference_kwargs = {
            k: v for k, v in model_config.items() if k in self._INFERENCE_KEYS
        }
        logger.info(f"Loading YOLO model from {model_path}")
        self._model = YOLO(str(model_path))
        logger.info("YOLO model loaded.")

    def run(self, frame: NDArray[np.uint8]) -> Results | None:
        """Run inference on a single frame.

        Uses ``model.track()`` when persist=True (multi-frame tracking),
        otherwise uses ``model.predict()``.

        Parameters
        ----------
        frame : NDArray[np.uint8]
            BGR frame array to run inference on.

        Returns
        -------
        Results | None
            YOLO Results object for the frame, or None if inference fails.
        """
        try:
            if self._persist:
                raw = self._model.track(frame, **self._inference_kwargs)
            else:
                raw = self._model.predict(frame, **self._inference_kwargs)
        except Exception as exc:
            logger.warning(f"Inference failed on frame: {exc}")
            return None

        if not raw:
            return None
        result: Results = raw[0]
        return result
