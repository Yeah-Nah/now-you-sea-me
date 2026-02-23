"""Video recording to disk with timestamped filenames."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from numpy.typing import NDArray


class CameraRecording:
    """Handles video recording with timestamps and saves to disk.

    Parameters
    ----------
    output_dir : Path
        Directory where recording files will be saved. Created if it
        does not exist.
    file_prefix : str
        Filename prefix. A timestamp and extension are appended automatically.
    """

    def __init__(self, output_dir: Path, file_prefix: str = "recording") -> None:
        self._output_dir = output_dir
        self._file_prefix = file_prefix
        self._writer: cv2.VideoWriter | None = None

    def start(self, frame_width: int, frame_height: int, fps: int) -> None:
        """Open the VideoWriter with a timestamped output filename.

        Creates the output directory if it does not already exist.

        Parameters
        ----------
        frame_width : int
            Width of frames in pixels.
        frame_height : int
            Height of frames in pixels.
        fps : int
            Frames per second for the output video.

        Raises
        ------
        RuntimeError
            If the VideoWriter cannot be opened (e.g. no write permissions).
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._file_prefix}_{timestamp}.mp4"
        output_path = self._output_dir / filename
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(
            str(output_path), fourcc, fps, (frame_width, frame_height)
        )
        if not self._writer.isOpened():
            logger.error(f"Failed to open VideoWriter at {output_path}")
            raise RuntimeError(f"Could not open video file for writing: {output_path}")
        logger.info(f"Recording started: {output_path}")

    def write(self, frame: NDArray[np.uint8]) -> None:
        """Write a single frame to the video file.

        Parameters
        ----------
        frame : NDArray[np.uint8]
            BGR frame array to write.
        """
        if self._writer is not None and self._writer.isOpened():
            self._writer.write(frame)

    def stop(self) -> None:
        """Release the VideoWriter and flush the file to disk."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None
            logger.info("Recording stopped.")
