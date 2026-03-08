"""Camera and model settings configuration."""

import os
import sys
from pathlib import Path

from loguru import logger

from .utils.config_utils import get_project_root, load_yaml


class Settings:
    """Loads and validates pipeline and model configuration.

    Resolves all relative paths to absolute paths anchored at the project
    root. Validates that required files exist before the pipeline starts.

    Parameters
    ----------
    pipeline_config_path : str | Path
        Path to pipeline_config.yaml.
    model_config_path : str | Path
        Path to model_config.yaml.
    """

    def __init__(
        self,
        pipeline_config_path: str | Path,
        model_config_path: str | Path,
        camera_config_path: str | Path,
    ) -> None:
        self._root = get_project_root()
        self.pipeline_config: dict[str, object] = load_yaml(pipeline_config_path)
        self.model_config: dict[str, object] = load_yaml(model_config_path)
        self.camera_config: dict[str, object] = load_yaml(camera_config_path)
        self.output_dir: Path = self._resolve_output_dir()
        self.model_path: Path = self._resolve_model_path()
        self._validate()

    def _resolve_output_dir(self) -> Path:
        raw = str(
            self.pipeline_config.get("camera_feed_output_dir", "output/recordings/")
        )
        return (self._root / raw).resolve()

    def _resolve_model_path(self) -> Path:
        model_filename = str(self.model_config.get("model", ""))
        return (self._root / "models" / model_filename).resolve()

    def _has_display(self) -> bool:
        """Return True if a display server is available for GUI output."""
        if sys.platform == "linux":
            return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        return True  # Windows and macOS are assumed to have a display

    def _validate(self) -> None:
        if self.inference_enabled and not self.model_path.exists():
            logger.error(f"Model file not found: {self.model_path}")
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if self.live_view_enabled and not self._has_display():
            logger.error(
                "live_view_enabled is True but no display detected."
                "Set live_view_enabled: False in configs/pipeline_config.yaml for headless operation."
            )
            raise OSError(
                "No display detected. Set 'live_view_enabled: False' in pipeline_config.yaml."
            )
        logger.debug(f"Settings validated. Project root: {self._root}")

    @property
    def inference_enabled(self) -> bool:
        """Whether to run YOLO inference on each frame."""
        return bool(self.pipeline_config.get("inference_enabled", False))

    @property
    def recording_enabled(self) -> bool:
        """Whether to record the camera feed to disk."""
        return bool(self.pipeline_config.get("recording_enabled", False))

    @property
    def live_view_enabled(self) -> bool:
        """Whether to display the camera feed in real-time."""
        return bool(self.pipeline_config.get("live_view_enabled", True))

    @property
    def record_gyroscope(self) -> bool:
        """Whether to capture gyroscope data from the IMU."""
        return bool(self.pipeline_config.get("record_gyroscope", False))

    @property
    def dev_or_pi(self) -> str:
        """Target runtime environment: 'dev' or 'pi'."""
        return str(self.pipeline_config.get("dev_or_pi", "dev"))

    @property
    def colour_camera_resolution(self) -> tuple[int, int]:
        """Output resolution for colour cameras (e.g. CAM_A)."""
        resolution: list[int] = self.camera_config.get(
            "colour_camera_resolution", [1920, 1080]
        )  # type: ignore[assignment]
        w, h = resolution[0], resolution[1]
        return int(w), int(h)

    @property
    def mono_camera_resolution(self) -> tuple[int, int]:
        """Output resolution for mono cameras (e.g. CAM_B, CAM_C)."""
        resolution: list[int] = self.camera_config.get(
            "mono_camera_resolution", [640, 400]
        )  # type: ignore[assignment]
        w, h = resolution[0], resolution[1]
        return int(w), int(h)
