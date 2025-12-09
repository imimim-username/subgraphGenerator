"""Configuration file I/O operations."""

import json
import logging
from pathlib import Path

from subgraph_wizard.config.model import SubgraphConfig
from subgraph_wizard.errors import ValidationError

logger = logging.getLogger(__name__)


def load_config(path: Path) -> SubgraphConfig:
    """Load a SubgraphConfig from a JSON file.
    
    Args:
        path: Path to the subgraph-config.json file.
    
    Returns:
        SubgraphConfig instance populated from the file.
    
    Raises:
        ValidationError: If the file cannot be read, parsed, or is missing required fields.
    """
    path = Path(path)
    
    if not path.exists():
        raise ValidationError(f"Configuration file not found: {path}")
    
    if not path.is_file():
        raise ValidationError(f"Configuration path is not a file: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in configuration file: {e}")
    except IOError as e:
        raise ValidationError(f"Could not read configuration file: {e}")
    
    # Validate required fields exist
    required_fields = ["name", "network", "output_dir", "mappings_mode"]
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        raise ValidationError(
            f"Configuration file is missing required fields: {', '.join(missing_fields)}"
        )
    
    # Validate contracts field if present
    if "contracts" in data and not isinstance(data["contracts"], list):
        raise ValidationError("'contracts' field must be a list")
    
    # Validate each contract has required fields
    for i, contract in enumerate(data.get("contracts", [])):
        contract_required = ["name", "address", "start_block", "abi_path"]
        contract_missing = [f for f in contract_required if f not in contract]
        if contract_missing:
            raise ValidationError(
                f"Contract at index {i} is missing required fields: {', '.join(contract_missing)}"
            )
    
    try:
        config = SubgraphConfig.from_dict(data)
        logger.debug(f"Loaded configuration from {path}")
        return config
    except KeyError as e:
        raise ValidationError(f"Configuration file is missing required field: {e}")


def save_config(config: SubgraphConfig, path: Path) -> None:
    """Save a SubgraphConfig to a JSON file.
    
    Args:
        config: SubgraphConfig instance to save.
        path: Path where the configuration file will be written.
    
    Raises:
        ValidationError: If the file cannot be written.
    """
    path = Path(path)
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = config.to_dict()
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved configuration to {path}")
    except IOError as e:
        raise ValidationError(f"Could not write configuration file: {e}")
