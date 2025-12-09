"""Configuration validation logic."""

import logging
import re

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.errors import ValidationError
from subgraph_wizard.networks import SUPPORTED_NETWORKS

logger = logging.getLogger(__name__)

# Valid mapping modes
VALID_MAPPING_MODES = {"stub", "auto"}

# Valid complexity levels (start with basic only as per milestone 2)
VALID_COMPLEXITY_LEVELS = {"basic"}

# Supported config versions
SUPPORTED_CONFIG_VERSIONS = {1}

# Regex for Ethereum address validation: 0x followed by exactly 40 hex characters
ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def validate_address(address: str, contract_name: str) -> None:
    """Validate an Ethereum address format.
    
    Args:
        address: Address string to validate.
        contract_name: Name of the contract (for error messages).
    
    Raises:
        ValidationError: If the address is not valid.
    """
    if not ADDRESS_PATTERN.match(address):
        raise ValidationError(
            f"Invalid address for contract '{contract_name}': '{address}'. "
            f"Address must be '0x' followed by 40 hexadecimal characters."
        )


def validate_contract(contract: ContractConfig) -> None:
    """Validate a single contract configuration.
    
    Args:
        contract: ContractConfig instance to validate.
    
    Raises:
        ValidationError: If the contract configuration is invalid.
    """
    # Validate contract name is non-empty
    if not contract.name or not contract.name.strip():
        raise ValidationError("Contract name cannot be empty")
    
    # Validate address format
    validate_address(contract.address, contract.name)
    
    # Validate start_block is non-negative
    if contract.start_block < 0:
        raise ValidationError(
            f"Invalid start_block for contract '{contract.name}': {contract.start_block}. "
            f"Start block must be a non-negative integer."
        )
    
    # Validate abi_path is non-empty
    if not contract.abi_path or not contract.abi_path.strip():
        raise ValidationError(
            f"ABI path cannot be empty for contract '{contract.name}'"
        )


def validate_config(config: SubgraphConfig) -> None:
    """Validate a SubgraphConfig.
    
    Performs comprehensive validation of the configuration:
    - Config version must be supported
    - Network must be in SUPPORTED_NETWORKS
    - All contract addresses must be valid
    - Mapping mode must be 'stub' or 'auto'
    - Complexity must be 'basic' (for now)
    
    Args:
        config: SubgraphConfig instance to validate.
    
    Raises:
        ValidationError: If validation fails, with a clear error message.
    """
    logger.debug(f"Validating configuration: {config.name}")
    
    # Validate config version
    if config.config_version not in SUPPORTED_CONFIG_VERSIONS:
        raise ValidationError(
            f"Unsupported config_version: {config.config_version}. "
            f"Supported versions: {sorted(SUPPORTED_CONFIG_VERSIONS)}"
        )
    
    # Validate subgraph name
    if not config.name or not config.name.strip():
        raise ValidationError("Subgraph name cannot be empty")
    
    # Validate network
    if config.network not in SUPPORTED_NETWORKS:
        supported = ", ".join(sorted(SUPPORTED_NETWORKS.keys()))
        raise ValidationError(
            f"Unknown network: '{config.network}'. Supported networks: {supported}"
        )
    
    # Validate output directory
    if not config.output_dir or not config.output_dir.strip():
        raise ValidationError("Output directory cannot be empty")
    
    # Validate mapping mode
    if config.mappings_mode not in VALID_MAPPING_MODES:
        raise ValidationError(
            f"Invalid mappings_mode: '{config.mappings_mode}'. "
            f"Must be one of: {', '.join(sorted(VALID_MAPPING_MODES))}"
        )
    
    # Validate complexity level
    if config.complexity not in VALID_COMPLEXITY_LEVELS:
        raise ValidationError(
            f"Invalid complexity: '{config.complexity}'. "
            f"Must be one of: {', '.join(sorted(VALID_COMPLEXITY_LEVELS))} "
            f"(intermediate and advanced will be supported in future milestones)"
        )
    
    # Validate contracts list is not empty
    if not config.contracts:
        raise ValidationError("At least one contract must be specified")
    
    # Validate each contract
    for contract in config.contracts:
        validate_contract(contract)
    
    # Check for duplicate contract names
    contract_names = [c.name for c in config.contracts]
    if len(contract_names) != len(set(contract_names)):
        duplicates = [name for name in contract_names if contract_names.count(name) > 1]
        raise ValidationError(
            f"Duplicate contract names found: {', '.join(set(duplicates))}"
        )
    
    # Check for duplicate contract addresses (same address indexed multiple times)
    contract_addresses = [c.address.lower() for c in config.contracts]
    if len(contract_addresses) != len(set(contract_addresses)):
        duplicates = [addr for addr in contract_addresses if contract_addresses.count(addr) > 1]
        raise ValidationError(
            f"Duplicate contract addresses found: {', '.join(set(duplicates))}"
        )
    
    logger.debug(f"Configuration validation passed for: {config.name}")
