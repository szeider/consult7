"""Configuration loader for custom providers."""

import logging
from pathlib import Path
from typing import List, Optional

import yaml

from .models import ConfigurationFile, CustomProviderConfig


logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and validates custom provider configurations."""

    @classmethod
    def load(cls) -> List[CustomProviderConfig]:
        """Load custom provider configurations from available config files.

        Returns:
            List of validated CustomProviderConfig objects
        """
        config_path = cls._discover_config_file()
        if not config_path:
            logger.debug("No custom provider configuration file found")
            return []

        try:
            config_data = cls._load_yaml_file(config_path)
            if not config_data:
                logger.debug(f"Empty or invalid configuration file: {config_path}")
                return []

            # Parse and validate using Pydantic
            config_file = ConfigurationFile(**config_data)

            logger.info(
                f"Loaded {len(config_file.custom_providers)} "
                f"custom providers from {config_path}"
            )
            return config_file.custom_providers

        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            return []

    @classmethod
    def _discover_config_file(cls) -> Optional[Path]:
        """Discover configuration file in repo root.

        Returns:
            Path to providers.yaml in repo root, or None if not found
        """
        # Get the repository root (where this package is installed)
        # Go up from src/consult7/config/loader.py to repo root
        repo_root = Path(__file__).parent.parent.parent.parent
        config_path = repo_root / "providers.yaml"

        if config_path.exists():
            logger.debug(f"Using config from repo root: {config_path}")
            return config_path

        logger.debug(f"No providers.yaml found at {config_path}")
        return None

    @classmethod
    def _load_yaml_file(cls, config_path: Path) -> Optional[dict]:
        """Load and parse YAML file.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            Parsed configuration dictionary, or None if failed
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                # Parse YAML directly
                config_data = yaml.safe_load(f)

            if not isinstance(config_data, dict):
                logger.error(
                    f"Configuration file must contain a dictionary "
                    f"at root level: {config_path}"
                )
                return None

            return config_data

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML syntax in {config_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to read configuration file {config_path}: {e}")
            return None

    @classmethod
    def get_config_location(cls) -> str:
        """Get the configuration file location for troubleshooting.

        Returns:
            Configuration file path
        """
        repo_root = Path(__file__).parent.parent.parent.parent
        return str(repo_root / "providers.yaml")
