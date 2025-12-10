"""Configuration validation logic."""

import logging
import re

from subgraph_wizard.config.model import (
    SubgraphConfig,
    ContractConfig,
    TemplateConfig,
    EntityRelationship,
)
from subgraph_wizard.errors import ValidationError
from subgraph_wizard.networks import SUPPORTED_NETWORKS

logger = logging.getLogger(__name__)

# Valid mapping modes
VALID_MAPPING_MODES = {"stub", "auto"}

# Valid complexity levels
VALID_COMPLEXITY_LEVELS = {"basic", "intermediate", "advanced"}

# Supported config versions
# Version 1: Basic complexity only (events)
# Version 2: Adds intermediate complexity (call/block handlers)
# Version 3: Adds advanced complexity (templates, relationships)
SUPPORTED_CONFIG_VERSIONS = {1, 2, 3}

# Valid relationship types for entity relationships
VALID_RELATION_TYPES = {"one_to_one", "one_to_many", "many_to_many"}

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


def validate_call_handler_signature(signature: str, contract_name: str) -> None:
    """Validate a call handler function signature.
    
    Call handler signatures should be in the format: functionName(type1,type2,...)
    
    Args:
        signature: Function signature string.
        contract_name: Name of the contract (for error messages).
    
    Raises:
        ValidationError: If the signature is invalid.
    """
    if not signature or not signature.strip():
        raise ValidationError(
            f"Empty call handler signature for contract '{contract_name}'"
        )
    
    # Basic format check: should have parentheses
    if "(" not in signature or ")" not in signature:
        raise ValidationError(
            f"Invalid call handler signature for contract '{contract_name}': '{signature}'. "
            f"Expected format: functionName(type1,type2,...)"
        )
    
    # Check function name is not empty
    func_name = signature.split("(")[0].strip()
    if not func_name:
        raise ValidationError(
            f"Call handler signature missing function name for contract '{contract_name}': '{signature}'"
        )


def validate_template(template: TemplateConfig, contract_names: set[str]) -> None:
    """Validate a template configuration (advanced complexity).
    
    Args:
        template: TemplateConfig instance to validate.
        contract_names: Set of valid contract names in the config.
    
    Raises:
        ValidationError: If the template configuration is invalid.
    """
    # Validate template name is non-empty
    if not template.name or not template.name.strip():
        raise ValidationError("Template name cannot be empty")
    
    # Validate abi_path is non-empty
    if not template.abi_path or not template.abi_path.strip():
        raise ValidationError(
            f"ABI path cannot be empty for template '{template.name}'"
        )
    
    # Validate source_contract references an existing contract
    if template.source_contract not in contract_names:
        raise ValidationError(
            f"Template '{template.name}' references unknown source_contract "
            f"'{template.source_contract}'. Must be one of: {', '.join(sorted(contract_names))}"
        )
    
    # Validate source_event is non-empty
    if not template.source_event or not template.source_event.strip():
        raise ValidationError(
            f"Source event cannot be empty for template '{template.name}'"
        )
    
    # Validate event_handlers is non-empty for templates
    if not template.event_handlers:
        raise ValidationError(
            f"Template '{template.name}' must have at least one event handler"
        )
    
    # Validate each event handler name is non-empty
    for handler in template.event_handlers:
        if not handler or not handler.strip():
            raise ValidationError(
                f"Empty event handler name in template '{template.name}'"
            )
    
    # Validate call handlers if provided
    if template.call_handlers:
        for signature in template.call_handlers:
            validate_call_handler_signature(signature, f"template:{template.name}")


def validate_entity_relationship(
    relationship: EntityRelationship,
    contract_names: set[str],
    template_names: set[str],
) -> None:
    """Validate an entity relationship configuration (advanced complexity).
    
    Args:
        relationship: EntityRelationship instance to validate.
        contract_names: Set of valid contract names in the config.
        template_names: Set of valid template names in the config.
    
    Raises:
        ValidationError: If the relationship configuration is invalid.
    """
    # Validate from_entity is non-empty
    if not relationship.from_entity or not relationship.from_entity.strip():
        raise ValidationError("Entity relationship 'from_entity' cannot be empty")
    
    # Validate to_entity is non-empty
    if not relationship.to_entity or not relationship.to_entity.strip():
        raise ValidationError("Entity relationship 'to_entity' cannot be empty")
    
    # Validate field_name is non-empty
    if not relationship.field_name or not relationship.field_name.strip():
        raise ValidationError(
            f"Entity relationship field_name cannot be empty "
            f"(from '{relationship.from_entity}' to '{relationship.to_entity}')"
        )
    
    # Validate relation_type is valid
    if relationship.relation_type not in VALID_RELATION_TYPES:
        raise ValidationError(
            f"Invalid relation_type '{relationship.relation_type}' in relationship "
            f"from '{relationship.from_entity}' to '{relationship.to_entity}'. "
            f"Must be one of: {', '.join(sorted(VALID_RELATION_TYPES))}"
        )
    
    # Note: We don't strictly validate that from_entity/to_entity match contract/template names
    # because entities can be generated from events and may have different names.
    # The actual entity names are determined at generation time based on ABI events.


def validate_contract(contract: ContractConfig, complexity: str = "basic") -> None:
    """Validate a single contract configuration.
    
    Args:
        contract: ContractConfig instance to validate.
        complexity: Complexity level of the subgraph config.
    
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
    
    # Validate intermediate complexity fields
    if complexity == "intermediate":
        # Validate call handlers if provided
        if contract.call_handlers:
            for signature in contract.call_handlers:
                validate_call_handler_signature(signature, contract.name)
        
        # block_handler is just a boolean, no additional validation needed
    elif complexity == "basic":
        # Warn if intermediate features are used with basic complexity
        if contract.call_handlers:
            logger.warning(
                f"Contract '{contract.name}' has call_handlers but complexity is 'basic'. "
                f"Call handlers will be ignored."
            )
        if contract.block_handler:
            logger.warning(
                f"Contract '{contract.name}' has block_handler enabled but complexity is 'basic'. "
                f"Block handler will be ignored."
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
            f"Must be one of: {', '.join(sorted(VALID_COMPLEXITY_LEVELS))}"
        )
    
    # Validate contracts list is not empty
    if not config.contracts:
        raise ValidationError("At least one contract must be specified")
    
    # Validate each contract, passing complexity for intermediate field validation
    for contract in config.contracts:
        validate_contract(contract, config.complexity)
    
    # Check for duplicate contract names
    contract_names = [c.name for c in config.contracts]
    contract_names_set = set(contract_names)
    if len(contract_names) != len(contract_names_set):
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
    
    # Validate advanced complexity features
    if config.complexity == "advanced":
        # Validate templates
        for template in config.templates:
            validate_template(template, contract_names_set)
        
        # Check for duplicate template names
        template_names = [t.name for t in config.templates]
        if len(template_names) != len(set(template_names)):
            duplicates = [name for name in template_names if template_names.count(name) > 1]
            raise ValidationError(
                f"Duplicate template names found: {', '.join(set(duplicates))}"
            )
        
        # Validate entity relationships
        template_names_set = set(template_names)
        for relationship in config.entity_relationships:
            validate_entity_relationship(
                relationship, contract_names_set, template_names_set
            )
    else:
        # Warn if advanced features are used with non-advanced complexity
        if config.templates:
            logger.warning(
                f"Config has {len(config.templates)} template(s) but complexity is "
                f"'{config.complexity}'. Templates will be ignored. "
                f"Set complexity to 'advanced' to enable templates."
            )
        if config.entity_relationships:
            logger.warning(
                f"Config has {len(config.entity_relationships)} entity relationship(s) "
                f"but complexity is '{config.complexity}'. Relationships will be ignored. "
                f"Set complexity to 'advanced' to enable entity relationships."
            )
    
    logger.debug(f"Configuration validation passed for: {config.name}")
