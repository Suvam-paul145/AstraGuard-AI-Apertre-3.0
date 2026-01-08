"""
Configuration File Loader Utility

Provides unified loading for YAML and JSON configuration files with automatic format detection.

Features:
- Automatic format detection based on file extension or content
- Support for both YAML and JSON formats
- Graceful error handling
- Type-safe loading with validation
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def load_config_file(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML or JSON file with automatic format detection.

    Args:
        file_path: Path to the configuration file

    Returns:
        Dict containing the loaded configuration

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is unsupported or content is invalid
        Exception: For other parsing errors
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    file_extension = Path(file_path).suffix.lower()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_extension == '.json':
                return json.load(f)
            elif file_extension in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
                if data is None:
                    raise ValueError("Configuration file is empty")
                return data
            else:
                # Try to detect format from content
                content = f.read()
                f.seek(0)  # Reset file pointer

                # Try JSON first
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass

                # Try YAML
                try:
                    data = yaml.safe_load(content)
                    if data is None:
                        raise ValueError("Configuration file is empty")
                    return data
                except yaml.YAMLError:
                    pass

                raise ValueError(f"Unsupported configuration file format: {file_path}")

    except Exception as e:
        logger.error(f"Failed to load configuration file {file_path}: {e}")
        raise


def find_config_file(base_name: str, search_paths: Optional[list] = None) -> Optional[str]:
    """
    Find a configuration file by trying different extensions and locations.

    Args:
        base_name: Base name of the config file (without extension)
        search_paths: List of directories to search in. If None, uses default paths.

    Returns:
        Path to the found config file, or None if not found
    """
    if search_paths is None:
        search_paths = ['config', '']

    extensions = ['.yaml', '.yml', '.json']

    for search_path in search_paths:
        for ext in extensions:
            candidate = os.path.join(search_path, f"{base_name}{ext}")
            if os.path.exists(candidate):
                logger.info(f"Found configuration file: {candidate}")
                return candidate

    return None


def save_config_file(file_path: str, config: Dict[str, Any], format: Optional[str] = None) -> None:
    """
    Save configuration to a file in YAML or JSON format.

    Args:
        file_path: Path where to save the configuration
        config: Configuration dictionary to save
        format: Format to use ('yaml', 'json', or None for auto-detection from extension)
    """
    if format is None:
        ext = Path(file_path).suffix.lower()
        if ext == '.json':
            format = 'json'
        else:
            format = 'yaml'

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        if format == 'json':
            json.dump(config, f, indent=2, ensure_ascii=False)
        elif format == 'yaml':
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format: {format}")

    logger.info(f"Saved configuration to {file_path}")