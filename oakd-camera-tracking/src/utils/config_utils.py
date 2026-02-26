"""Config loading utilities for oakd-camera-tracking."""

from pathlib import Path

import yaml
from loguru import logger


def get_project_root() -> Path:
    """Return the absolute path to the oakd-camera-tracking project root.

    This file lives at src/utils/config_utils.py, so the project root is
    three levels up from this file.
    """
    if __file__ is None:
        raise RuntimeError("__file__ is not available in this context")
    return Path(__file__).resolve().parent.parent.parent


def load_yaml(path: str | Path) -> dict[str, object]:
    """Load a YAML file and return its contents as a dictionary.

    Parameters
    ----------
    path : str | Path
        Path to the YAML file to load.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at the given path.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        logger.error(f"Config file not found: {resolved}")
        raise FileNotFoundError(f"Config file not found: {resolved}")
    with resolved.open("r") as f:
        data = yaml.safe_load(f)
    if data is None:
        logger.error(f"Config file is empty: {resolved}")
        raise ValueError(f"Config file is empty: {resolved}")
    logger.debug(f"Loaded config from {resolved}")
    return data  # type: ignore[no-any-return]
