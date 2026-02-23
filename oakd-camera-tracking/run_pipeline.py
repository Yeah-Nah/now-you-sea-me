"""Entry point for the oakd-camera-tracking pipeline.

Connects to the OAK-D camera, optionally runs YOLO inference for boat
detection, and records the feed based on configuration.

Usage
-----
    python run_pipeline.py
    python run_pipeline.py --pipeline-config configs/pipline_config.yaml
    python run_pipeline.py --model-config configs/model_config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger


def _add_src_to_path() -> None:
    """Insert the src/ directory into sys.path for module imports."""
    src_dir = Path(__file__).resolve().parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


def main() -> None:
    """Parse arguments, load settings, and run the pipeline."""
    _add_src_to_path()

    # Deferred imports — sys.path must be updated before these resolve.
    from pipeline import Pipeline
    from settings import Settings

    parser = argparse.ArgumentParser(description="OAK-D camera tracking pipeline.")
    parser.add_argument(
        "--pipeline-config",
        default="configs/pipline_config.yaml",
        help="Path to the pipeline config YAML (default: configs/pipline_config.yaml)",
    )
    parser.add_argument(
        "--model-config",
        default="configs/model_config.yaml",
        help="Path to the model config YAML (default: configs/model_config.yaml)",
    )
    args = parser.parse_args()

    logger.info("Loading configuration...")
    try:
        settings = Settings(
            pipeline_config_path=args.pipeline_config,
            model_config_path=args.model_config,
        )
    except FileNotFoundError as exc:
        logger.error(f"Configuration error: {exc}")
        sys.exit(1)

    pipeline = Pipeline(settings)
    pipeline.run()


if __name__ == "__main__":
    main()
