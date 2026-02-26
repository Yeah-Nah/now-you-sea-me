"""Entry point for the oakd-camera-tracking pipeline.

Connects to the OAK-D camera, optionally runs YOLO inference for boat
detection, and records the feed based on configuration.

Usage
-----
    python run_pipeline.py
    python run_pipeline.py --pipeline-config configs/pipeline_config.yaml
    python run_pipeline.py --model-config configs/model_config.yaml
"""

from __future__ import annotations

import argparse
import sys

from loguru import logger
from src.pipeline import Pipeline
from src.settings import Settings


def main() -> None:
    """Parse arguments, load settings, and run the pipeline."""
    parser = argparse.ArgumentParser(description="OAK-D camera tracking pipeline.")
    parser.add_argument(
        "--pipeline-config",
        default="configs/pipeline_config.yaml",
        help="Path to the pipeline config YAML",
    )
    parser.add_argument(
        "--model-config",
        default="configs/model_config.yaml",
        help="Path to the model config YAML",
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
