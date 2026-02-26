"""Video recording to disk with timestamped filenames."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING

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
        self._timestamp: str = ""

    @property
    def timestamp(self) -> str:
        """Datetime string generated when recording started (``YYYYMMDD_HHMMSS``)."""
        return self._timestamp

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
        self._timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._file_prefix}_{self._timestamp}.mp4"
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


class GyroRecorder:
    """Records gyroscope readings to a JSONL file on disk.

    Each line in the output file is a JSON object with keys
    ``timestamp_s``, ``x``, ``y``, and ``z``.

    Parameters
    ----------
    output_dir : Path
        Directory where the JSONL file will be saved. Created if it
        does not exist.
    file_prefix : str
        Filename prefix. A timestamp and extension are appended automatically.
    """

    def __init__(self, output_dir: Path, file_prefix: str = "recording") -> None:
        self._output_dir = output_dir
        self._file_prefix = file_prefix
        self._file: IO[str] | None = None

    def start(self, timestamp: str | None = None) -> None:
        """Open the JSONL file for writing.

        Parameters
        ----------
        timestamp : str | None
            Datetime string in ``YYYYMMDD_HHMMSS`` format. Pass the value from
            ``CameraRecording.timestamp`` to produce a matching filename. If
            None, a new timestamp is generated.
        """
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"{self._file_prefix}_{ts}.jsonl"
        self._file = path.open("w", encoding="utf-8")
        logger.info(f"Gyroscope recording started: {path}")

    def write(self, readings: list[dict[str, float]]) -> None:
        """Append gyroscope readings to the JSONL file.

        Parameters
        ----------
        readings : list[dict[str, float]]
            Parsed gyroscope readings as returned by
            ``CameraAccess.get_gyro_data()``.
        """
        if self._file is not None:
            for reading in readings:
                self._file.write(json.dumps(reading) + "\n")

    def stop(self) -> None:
        """Close and flush the JSONL file."""
        if self._file is not None:
            self._file.close()
            self._file = None
            logger.info("Gyroscope recording stopped.")
