"""Configuration loader for custom providers."""

import logging
import os
import re
from pathlib import Path
from typing import List, Optional

import yaml
from platformdirs import user_config_dir

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
            
            logger.info(f"Loaded {len(config_file.custom_providers)} custom providers from {config_path}")
            return config_file.custom_providers
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            return []
    
    @classmethod
    def _discover_config_file(cls) -> Optional[Path]:
        """Discover configuration file using priority hierarchy.
        
        Priority order:
        1. CONSULT7_CONFIG_PATH environment variable
        2. ./providers.yaml (project-specific)
        3. ~/.config/consult7/providers.yaml (user-global) 
        4. /etc/consult7/providers.yaml (system-wide)
        
        Returns:
            Path to first existing configuration file, or None
        """
        # 1. Environment variable override
        env_path = os.getenv("CONSULT7_CONFIG_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.debug(f"Using config from CONSULT7_CONFIG_PATH: {path}")
                return path
            else:
                logger.warning(f"CONSULT7_CONFIG_PATH points to non-existent file: {path}")
        
        # 2. Project-specific
        project_config = Path.cwd() / "providers.yaml"
        if project_config.exists():
            logger.debug(f"Using project-specific config: {project_config}")
            return project_config
        
        # 3. User-global
        user_config = Path(user_config_dir("consult7")) / "providers.yaml"
        if user_config.exists():
            logger.debug(f"Using user config: {user_config}")
            return user_config
        
        # 4. System-wide (Unix-like systems only)
        if os.name != "nt":  # Not Windows
            system_config = Path("/etc/consult7/providers.yaml")
            if system_config.exists():
                logger.debug(f"Using system config: {system_config}")
                return system_config
        
        logger.debug("No configuration file found in any location")
        return None
    
    @classmethod
    def _load_yaml_file(cls, config_path: Path) -> Optional[dict]:
        """Load and parse YAML file with environment variable substitution.
        
        Args:
            config_path: Path to the YAML configuration file
            
        Returns:
            Parsed configuration dictionary, or None if failed
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Perform environment variable substitution
            content = cls._substitute_env_vars(content)
            
            # Parse YAML
            config_data = yaml.safe_load(content)
            
            if not isinstance(config_data, dict):
                logger.error(f"Configuration file must contain a dictionary at root level: {config_path}")
                return None
            
            return config_data
            
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML syntax in {config_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to read configuration file {config_path}: {e}")
            return None
    
    @classmethod
    def _substitute_env_vars(cls, content: str) -> str:
        """Substitute environment variables in configuration content.
        
        Supports ${VAR_NAME} and ${VAR_NAME:-default_value} syntax.
        
        Args:
            content: Raw configuration file content
            
        Returns:
            Content with environment variables substituted
        """
        def replace_env_var(match):
            var_expr = match.group(1)
            
            # Check for default value syntax: VAR_NAME:-default
            if ":-" in var_expr:
                var_name, default_value = var_expr.split(":-", 1)
                return os.getenv(var_name.strip(), default_value.strip())
            else:
                # No default value specified
                var_name = var_expr.strip()
                value = os.getenv(var_name)
                if value is None:
                    logger.warning(f"Environment variable '{var_name}' not set and no default provided")
                    return f"${{{var_name}}}"  # Leave unchanged if not found
                return value
        
        # Pattern matches ${VAR_NAME} and ${VAR_NAME:-default}
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_env_var, content)
    
    @classmethod
    def get_config_locations(cls) -> List[str]:
        """Get list of all configuration file locations for troubleshooting.
        
        Returns:
            List of configuration file paths in priority order
        """
        locations = []
        
        # Environment variable location
        env_path = os.getenv("CONSULT7_CONFIG_PATH")
        if env_path:
            locations.append(f"CONSULT7_CONFIG_PATH: {env_path}")
        
        # Standard locations
        locations.extend([
            f"Project: {Path.cwd() / 'providers.yaml'}",
            f"User: {Path(user_config_dir('consult7')) / 'providers.yaml'}",
        ])
        
        if os.name != "nt":
            locations.append("System: /etc/consult7/providers.yaml")
        
        return locations