"""Interactive wizard for collecting subgraph configuration from user.

This module implements the guided Q&A wizard that walks users through
creating a subgraph configuration, including:
- Subgraph name and network selection
- Contract configuration (name, address, start block)
- ABI acquisition (file, paste, or Etherscan fetch)
- Mapping mode selection
"""

import logging
from pathlib import Path
from typing import Any

from subgraph_wizard.config.model import (
    SubgraphConfig,
    ContractConfig,
    TemplateConfig,
    EntityRelationship,
)
from subgraph_wizard.config.io import save_config
from subgraph_wizard.config.validation import validate_config
from subgraph_wizard.networks import SUPPORTED_NETWORKS
from subgraph_wizard.abi.local import load_abi_from_file, write_abi_to_file
from subgraph_wizard.abi.paste import load_abi_interactive
from subgraph_wizard.abi.etherscan import fetch_abi_from_explorer, get_supported_networks_for_explorer
from subgraph_wizard.errors import SubgraphWizardError, ValidationError, AbiFetchError
from subgraph_wizard.utils.prompts_utils import ask_string, ask_choice, ask_yes_no, ask_int, ask_string_list

logger = logging.getLogger(__name__)


def _validate_contract_address(address: str) -> bool:
    """Validate an Ethereum address format.
    
    Args:
        address: Address string to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    pattern = re.compile(r"^0x[a-fA-F0-9]{40}$")
    return bool(pattern.match(address))


def _validate_contract_name(name: str) -> bool:
    """Validate a contract name.
    
    Contract names should be alphanumeric (with underscores) and not empty.
    
    Args:
        name: Contract name to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    # Allow alphanumeric and underscores, must start with letter
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
    return bool(pattern.match(name))


def _validate_subgraph_name(name: str) -> bool:
    """Validate a subgraph name.
    
    Subgraph names should be lowercase alphanumeric with hyphens allowed.
    
    Args:
        name: Subgraph name to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    # Allow lowercase alphanumeric and hyphens, must start with letter
    pattern = re.compile(r"^[a-z][a-z0-9\-]*$")
    return bool(pattern.match(name))


def _get_abi_from_file() -> list[dict[str, Any]]:
    """Get ABI by loading from a local file.
    
    Returns:
        The loaded ABI.
    
    Raises:
        AbiFetchError: If file cannot be loaded.
        ValidationError: If ABI is invalid.
    """
    while True:
        file_path = ask_string("Enter path to ABI JSON file")
        path = Path(file_path).expanduser().resolve()
        
        try:
            abi = load_abi_from_file(path)
            logger.info(f"Successfully loaded ABI with {len(abi)} entries")
            return abi
        except (AbiFetchError, ValidationError) as e:
            print(f"Error: {e}")
            if not ask_yes_no("Try another file?", default=True):
                raise


def _get_abi_from_paste() -> list[dict[str, Any]]:
    """Get ABI by having user paste JSON.
    
    Returns:
        The loaded ABI.
    
    Raises:
        ValidationError: If ABI is invalid.
    """
    while True:
        try:
            abi = load_abi_interactive()
            logger.info(f"Successfully parsed ABI with {len(abi)} entries")
            return abi
        except ValidationError as e:
            print(f"Error: {e}")
            if not ask_yes_no("Try pasting again?", default=True):
                raise


def _get_abi_from_explorer(network: str, address: str) -> list[dict[str, Any]]:
    """Get ABI by fetching from explorer API.
    
    Args:
        network: Network name.
        address: Contract address.
    
    Returns:
        The fetched ABI.
    
    Raises:
        AbiFetchError: If ABI cannot be fetched.
    """
    print(f"\nFetching ABI from {network} explorer for {address}...")
    
    try:
        abi = fetch_abi_from_explorer(network, address)
        logger.info(f"Successfully fetched ABI with {len(abi)} entries")
        return abi
    except AbiFetchError as e:
        print(f"Error: {e}")
        raise


def _get_abi_for_contract(
    contract_name: str,
    network: str,
    address: str
) -> list[dict[str, Any]]:
    """Get ABI for a contract through user-selected method.
    
    Args:
        contract_name: Name of the contract.
        network: Network name.
        address: Contract address.
    
    Returns:
        The ABI data.
    
    Raises:
        SubgraphWizardError: If ABI cannot be obtained.
    """
    # Check if explorer fetch is available for this network
    explorer_networks = get_supported_networks_for_explorer()
    explorer_available = network in explorer_networks
    
    # Build options list
    options = ["Local file", "Paste JSON"]
    if explorer_available:
        options.append("Fetch from explorer")
    
    print(f"\nHow would you like to provide the ABI for '{contract_name}'?")
    choice = ask_choice("Select ABI source", options, default_index=0)
    
    if choice == "Local file":
        return _get_abi_from_file()
    elif choice == "Paste JSON":
        return _get_abi_from_paste()
    elif choice == "Fetch from explorer":
        return _get_abi_from_explorer(network, address)
    else:
        raise SubgraphWizardError(f"Unknown ABI source: {choice}")


def _validate_call_handler_signature(signature: str) -> bool:
    """Validate a call handler function signature format.
    
    Args:
        signature: Function signature to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    if not signature or "(" not in signature or ")" not in signature:
        return False
    func_name = signature.split("(")[0].strip()
    return bool(func_name)


def _validate_template_name(name: str) -> bool:
    """Validate a template name.
    
    Template names should be alphanumeric (with underscores) and not empty.
    Similar to contract names.
    
    Args:
        name: Template name to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    # Allow alphanumeric and underscores, must start with letter
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
    return bool(pattern.match(name))


def _validate_event_name(name: str) -> bool:
    """Validate an event name.
    
    Event names should be alphanumeric (with underscores) and not empty.
    
    Args:
        name: Event name to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    # Allow alphanumeric and underscores, must start with letter
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
    return bool(pattern.match(name))


def _validate_entity_name(name: str) -> bool:
    """Validate an entity name.
    
    Entity names should be alphanumeric (with underscores) and not empty.
    Typically PascalCase but not enforced.
    
    Args:
        name: Entity name to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    # Allow alphanumeric and underscores, must start with letter
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
    return bool(pattern.match(name))


def _validate_field_name(name: str) -> bool:
    """Validate a field name.
    
    Field names should be alphanumeric (with underscores) and not empty.
    Typically camelCase but not enforced.
    
    Args:
        name: Field name to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    # Allow alphanumeric and underscores, must start with letter (lowercase for GraphQL convention)
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
    return bool(pattern.match(name))


def _collect_template(
    existing_template_names: set[str],
    contract_names: list[str],
) -> TemplateConfig:
    """Collect configuration for a dynamic data source template.
    
    Args:
        existing_template_names: Set of already-used template names.
        contract_names: List of contract names that can be the source for this template.
    
    Returns:
        TemplateConfig for the template.
    """
    print("\n--- Template Configuration ---")
    print("Templates define dynamic data sources that are instantiated at runtime.")
    print("For example, a factory contract creates new contracts that should be indexed.\n")
    
    # Get template name
    while True:
        name = ask_string(
            "Template name (e.g., Pair, Pool, Vault)",
            validator=_validate_template_name,
            error_message="Invalid name. Use letters, numbers, and underscores. Must start with a letter."
        )
        if name in existing_template_names:
            print(f"A template named '{name}' already exists. Please choose a different name.")
            continue
        break
    
    # Get ABI path
    abi_path = ask_string(
        f"ABI filename for {name} (e.g., {name}.json)",
        default=f"{name}.json"
    )
    
    # Get source contract (the factory contract that creates instances)
    print(f"\nWhich contract creates/instantiates {name} instances?")
    source_contract = ask_choice(
        "Select source (factory) contract",
        contract_names,
        default_index=0
    )
    
    # Get source event (the event that signals a new instance)
    source_event = ask_string(
        f"Event name that signals new {name} creation (e.g., PairCreated, PoolCreated)",
        validator=_validate_event_name,
        error_message="Invalid event name. Use letters, numbers, and underscores. Must start with a letter."
    )
    
    # Get event handlers for the template
    print(f"\nWhat events should be indexed from {name} instances?")
    event_handlers = ask_string_list(
        f"Enter event names to handle in {name}:",
        item_name="event name",
        validator=_validate_event_name,
        error_message="Invalid event name. Use letters, numbers, and underscores. Must start with a letter."
    )
    
    if not event_handlers:
        # Require at least one event handler
        print("⚠️  At least one event handler is required. Adding 'Transfer' as default.")
        event_handlers = ["Transfer"]
    
    # Ask about index_events
    index_events = ask_yes_no(
        f"Index all events from {name} instances (recommended)?",
        default=True
    )
    
    # Ask about call handlers
    call_handlers: list[str] | None = None
    if ask_yes_no(f"Enable call handlers for {name}?", default=False):
        print(f"\nCall handlers index function calls to {name} contracts.")
        print("Example signatures: transfer(address,uint256), approve(address,uint256)")
        
        call_handlers = ask_string_list(
            "Enter function signatures to index:",
            item_name="signature",
            validator=_validate_call_handler_signature,
            error_message="Invalid signature format. Use: functionName(type1,type2,...)"
        )
        
        if not call_handlers:
            call_handlers = None
    
    # Ask about block handler
    block_handler = ask_yes_no(
        f"Enable block handler for {name} instances?",
        default=False
    )
    
    return TemplateConfig(
        name=name,
        abi_path=abi_path,
        event_handlers=event_handlers,
        source_contract=source_contract,
        source_event=source_event,
        index_events=index_events,
        call_handlers=call_handlers,
        block_handler=block_handler,
    )


def _collect_entity_relationship(
    existing_relationships: list[EntityRelationship],
) -> EntityRelationship:
    """Collect configuration for an entity relationship.
    
    Args:
        existing_relationships: List of already-defined relationships.
    
    Returns:
        EntityRelationship for the relationship.
    """
    print("\n--- Entity Relationship Configuration ---")
    print("Relationships define how entities reference each other in the schema.")
    print("Example: A Pool entity has a 'factory' field referencing a Factory entity.\n")
    
    # Get from_entity
    from_entity = ask_string(
        "Source entity name (entity that will have the field)",
        validator=_validate_entity_name,
        error_message="Invalid entity name. Use letters, numbers, and underscores. Must start with a letter."
    )
    
    # Get to_entity
    to_entity = ask_string(
        "Target entity name (entity being referenced)",
        validator=_validate_entity_name,
        error_message="Invalid entity name. Use letters, numbers, and underscores. Must start with a letter."
    )
    
    # Get field_name
    print(f"\nWhat should the field be named on {from_entity}?")
    default_field = to_entity[0].lower() + to_entity[1:] if to_entity else "reference"
    field_name = ask_string(
        f"Field name (e.g., {default_field})",
        default=default_field,
        validator=_validate_field_name,
        error_message="Invalid field name. Use letters, numbers, and underscores. Must start with a letter."
    )
    
    # Get relation_type
    print(f"\nRelationship type from {from_entity} to {to_entity}:")
    print("  - one_to_one: Single reference (e.g., Pool -> Factory)")
    print("  - one_to_many: Array of references (e.g., Factory -> [Pool])")
    print("  - many_to_many: Many-to-many relationship (e.g., User <-> Token)")
    relation_type = ask_choice(
        "Select relationship type",
        ["one_to_one", "one_to_many", "many_to_many"],
        default_index=0
    )
    
    # Get derived_from (optional, for reverse lookups)
    derived_from: str | None = None
    if ask_yes_no(f"Is {field_name} a derived field (computed from reverse lookup)?", default=False):
        derived_from = ask_string(
            f"Field on {to_entity} that references back to {from_entity}",
            validator=_validate_field_name,
            error_message="Invalid field name. Use letters, numbers, and underscores. Must start with a letter."
        )
    
    return EntityRelationship(
        from_entity=from_entity,
        to_entity=to_entity,
        relation_type=relation_type,
        field_name=field_name,
        derived_from=derived_from,
    )


def _collect_contract(
    network: str,
    existing_names: set[str],
    existing_addresses: set[str],
    complexity: str = "basic"
) -> ContractConfig:
    """Collect configuration for a single contract.
    
    Args:
        network: Network name (for explorer fetch).
        existing_names: Set of already-used contract names.
        existing_addresses: Set of already-used contract addresses.
        complexity: Complexity level ('basic', 'intermediate', or 'advanced').
    
    Returns:
        ContractConfig for the contract.
    """
    print("\n--- Contract Configuration ---")
    
    # Get contract name
    while True:
        name = ask_string(
            "Contract name (e.g., MyToken)",
            validator=_validate_contract_name,
            error_message="Invalid name. Use letters, numbers, and underscores. Must start with a letter."
        )
        if name in existing_names:
            print(f"A contract named '{name}' already exists. Please choose a different name.")
            continue
        break
    
    # Get contract address
    while True:
        address = ask_string(
            "Contract address (0x...)",
            validator=_validate_contract_address,
            error_message="Invalid address. Must be 0x followed by 40 hex characters."
        )
        address_lower = address.lower()
        if address_lower in existing_addresses:
            print(f"Address {address} is already being indexed. Please use a different address.")
            continue
        break
    
    # Get start block
    start_block = ask_int(
        "Start block (block number to start indexing from)",
        default=0,
        min_value=0
    )
    
    # ABI path will be set later after writing the ABI
    # For now, use the contract name
    abi_path = f"{name}.json"
    
    # Initialize intermediate complexity fields
    call_handlers: list[str] | None = None
    block_handler = False
    
    # Collect intermediate/advanced complexity options if applicable
    if complexity in ("intermediate", "advanced"):
        print("\n--- Advanced Handler Options ---")
        
        # Ask about call handlers
        if ask_yes_no("Enable call handlers for this contract?", default=False):
            print("\nCall handlers index function calls to the contract.")
            print("Example signatures: transfer(address,uint256), approve(address,uint256)")
            
            call_handlers = ask_string_list(
                "Enter function signatures to index:",
                item_name="signature",
                validator=_validate_call_handler_signature,
                error_message="Invalid signature format. Use: functionName(type1,type2,...)"
            )
            
            if not call_handlers:
                print("No call handlers added.")
                call_handlers = None
            else:
                print(f"✓ Added {len(call_handlers)} call handler(s)")
        
        # Ask about block handler
        block_handler = ask_yes_no(
            "Enable block handler for this contract? (indexes every block)",
            default=False
        )
        if block_handler:
            print("✓ Block handler enabled")
    
    return ContractConfig(
        name=name,
        address=address,
        start_block=start_block,
        abi_path=abi_path,
        index_events=True,
        call_handlers=call_handlers,
        block_handler=block_handler
    )


def run_wizard() -> SubgraphConfig:
    """Run the interactive wizard to collect subgraph configuration.
    
    Walks the user through:
    1. Subgraph name and network selection
    2. Output directory
    3. Complexity (forced to 'basic' for now)
    4. Mapping mode (stub vs auto)
    5. Contract configuration loop (name, address, ABI)
    
    Returns:
        A validated SubgraphConfig.
    
    Raises:
        SubgraphWizardError: If wizard cannot complete.
        KeyboardInterrupt: If user cancels.
    """
    print("\n" + "=" * 60)
    print("  Subgraph Wizard - Interactive Configuration")
    print("=" * 60)
    print("\nThis wizard will help you create a subgraph configuration.")
    print("Press Ctrl+C at any time to cancel.\n")
    
    # Step 1: Subgraph name
    subgraph_name = ask_string(
        "Subgraph name (lowercase, e.g., my-token-subgraph)",
        validator=_validate_subgraph_name,
        error_message="Invalid name. Use lowercase letters, numbers, and hyphens. Must start with a letter."
    )
    
    # Step 2: Network selection
    networks = sorted(SUPPORTED_NETWORKS.keys())
    network = ask_choice(
        "Select target network",
        networks,
        default_index=0  # ethereum is typically first alphabetically
    )
    
    # Step 3: Output directory
    default_output_dir = subgraph_name
    output_dir = ask_string(
        "Output directory",
        default=default_output_dir
    )
    
    # Step 4: Complexity level selection
    print("\nComplexity level determines which indexing features are available:")
    print("  - basic: Index events only (recommended for most use cases)")
    print("  - intermediate: Events + call handlers + block handlers")
    print("  - advanced: All features + dynamic data sources (templates) + entity relationships")
    complexity = ask_choice(
        "Select complexity level",
        ["basic", "intermediate", "advanced"],
        default_index=0
    )
    
    if complexity == "intermediate":
        print("\n📋 Intermediate mode enabled!")
        print("   You can configure call handlers and block handlers for each contract.")
    elif complexity == "advanced":
        print("\n🚀 Advanced mode enabled!")
        print("   You can configure:")
        print("   - Call handlers and block handlers for each contract")
        print("   - Dynamic data source templates (e.g., factory patterns)")
        print("   - Entity relationships for schema generation")
    
    # Step 5: Mapping mode
    print("\nMapping mode determines how event handlers are generated:")
    print("  - auto: Fully functional handlers that save event data to entities")
    print("  - stub: Template handlers with TODO comments for custom implementation")
    mapping_mode = ask_choice(
        "Select mapping mode",
        ["auto", "stub"],
        default_index=0
    )
    
    if mapping_mode == "stub":
        print("\n⚠️  Note: Stub mappings will be generated in a future milestone.")
        print("    For now, only auto mode is fully functional.")
        print("    Your selection will be saved, and stub mappings will work")
        print("    once that feature is implemented.")
    
    # Step 6: Collect contracts
    contracts: list[ContractConfig] = []
    abis: dict[str, list[dict[str, Any]]] = {}
    existing_names: set[str] = set()
    existing_addresses: set[str] = set()
    
    print("\n" + "-" * 40)
    print("Contract Configuration")
    print("-" * 40)
    print("\nYou'll now add contracts to index.")
    print("You must add at least one contract.\n")
    
    while True:
        # Collect contract info
        contract = _collect_contract(network, existing_names, existing_addresses, complexity)
        
        # Get ABI for this contract
        try:
            abi = _get_abi_for_contract(contract.name, network, contract.address)
        except SubgraphWizardError as e:
            print(f"\nFailed to get ABI: {e}")
            if ask_yes_no("Skip this contract and continue?", default=False):
                continue
            else:
                raise
        
        # Store contract and ABI
        contracts.append(contract)
        abis[contract.name] = abi
        existing_names.add(contract.name)
        existing_addresses.add(contract.address.lower())
        
        print(f"\n✓ Added contract: {contract.name} ({contract.address})")
        
        # Ask about adding more contracts
        if not ask_yes_no("\nAdd another contract?", default=False):
            break
    
    # Collect advanced complexity features: templates and entity relationships
    templates: list[TemplateConfig] = []
    entity_relationships: list[EntityRelationship] = []
    template_abis: dict[str, list[dict[str, Any]]] = {}
    
    if complexity == "advanced":
        # Collect templates (dynamic data sources)
        print("\n" + "-" * 40)
        print("Dynamic Data Source Templates")
        print("-" * 40)
        print("\nTemplates are used to index contracts created at runtime.")
        print("For example: Uniswap V2 Factory creates Pair contracts dynamically.")
        
        existing_template_names: set[str] = set()
        contract_names_list = [c.name for c in contracts]
        
        if ask_yes_no("\nDo you want to add dynamic data source templates?", default=False):
            while True:
                template = _collect_template(existing_template_names, contract_names_list)
                
                # Get ABI for this template
                print(f"\nProvide ABI for template '{template.name}':")
                try:
                    template_abi = _get_abi_for_contract(
                        template.name,
                        network,
                        "0x0000000000000000000000000000000000000000"  # Placeholder - templates don't have fixed address
                    )
                except SubgraphWizardError as e:
                    print(f"\nFailed to get ABI: {e}")
                    if ask_yes_no("Skip this template and continue?", default=False):
                        continue
                    else:
                        raise
                
                templates.append(template)
                template_abis[template.name] = template_abi
                existing_template_names.add(template.name)
                
                print(f"\n✓ Added template: {template.name}")
                print(f"   Source: {template.source_contract}.{template.source_event}")
                print(f"   Event handlers: {', '.join(template.event_handlers)}")
                
                if not ask_yes_no("\nAdd another template?", default=False):
                    break
        
        # Collect entity relationships
        print("\n" + "-" * 40)
        print("Entity Relationships")
        print("-" * 40)
        print("\nRelationships define how entities reference each other in the schema.")
        print("This enables generating proper GraphQL relationships and derived fields.")
        
        if ask_yes_no("\nDo you want to define entity relationships?", default=False):
            while True:
                relationship = _collect_entity_relationship(entity_relationships)
                entity_relationships.append(relationship)
                
                print(f"\n✓ Added relationship: {relationship.from_entity}.{relationship.field_name} -> {relationship.to_entity}")
                print(f"   Type: {relationship.relation_type}")
                if relationship.derived_from:
                    print(f"   Derived from: {relationship.to_entity}.{relationship.derived_from}")
                
                if not ask_yes_no("\nAdd another relationship?", default=False):
                    break
    
    # Expand ~ to user's home directory before building config
    output_path = Path(output_dir).expanduser()
    expanded_output_dir = str(output_path)
    
    # Determine config version based on complexity
    if complexity == "advanced":
        config_version = 3
    elif complexity == "intermediate":
        config_version = 2
    else:
        config_version = 1
    
    # Build the config
    config = SubgraphConfig(
        name=subgraph_name,
        network=network,
        output_dir=expanded_output_dir,
        mappings_mode=mapping_mode,
        contracts=contracts,
        config_version=config_version,
        complexity=complexity,
        templates=templates,
        entity_relationships=entity_relationships,
    )
    
    # Validate the config
    print("\nValidating configuration...")
    try:
        validate_config(config)
        print("✓ Configuration is valid")
    except ValidationError as e:
        print(f"\n❌ Validation failed: {e}")
        raise
    
    # Create output directory structure and write ABIs
    print(f"\nCreating project structure in: {output_path}")
    abis_dir = output_path / "abis"
    abis_dir.mkdir(parents=True, exist_ok=True)
    
    # Write ABIs to files
    for contract in contracts:
        abi = abis[contract.name]
        abi_path = abis_dir / contract.abi_path
        write_abi_to_file(abi, abi_path)
        print(f"  ✓ Wrote ABI: {abi_path}")
    
    # Write template ABIs (for advanced complexity)
    for template in templates:
        if template.name in template_abis:
            abi = template_abis[template.name]
            abi_path = abis_dir / template.abi_path
            write_abi_to_file(abi, abi_path)
            print(f"  ✓ Wrote template ABI: {abi_path}")
    
    # Save config file
    config_path = output_path / "subgraph-config.json"
    save_config(config, config_path)
    print(f"  ✓ Saved config: {config_path}")
    
    print("\n" + "=" * 60)
    print("  Configuration Complete!")
    print("=" * 60)
    print(f"\nSubgraph: {config.name}")
    print(f"Network: {config.network}")
    print(f"Complexity: {config.complexity}")
    print(f"Contracts: {len(config.contracts)}")
    print(f"Mapping mode: {config.mappings_mode}")
    print(f"Output: {config.output_dir}")
    
    # Show intermediate/advanced features summary
    if config.complexity in ("intermediate", "advanced"):
        contracts_with_call = [c.name for c in config.contracts if c.call_handlers]
        contracts_with_block = [c.name for c in config.contracts if c.block_handler]
        
        if contracts_with_call:
            print(f"\nContracts with call handlers: {', '.join(contracts_with_call)}")
        if contracts_with_block:
            print(f"Contracts with block handlers: {', '.join(contracts_with_block)}")
    
    # Show advanced features summary
    if config.complexity == "advanced":
        if config.templates:
            print(f"\nTemplates: {len(config.templates)}")
            for t in config.templates:
                print(f"  - {t.name} (from {t.source_contract}.{t.source_event})")
        
        if config.entity_relationships:
            print(f"\nEntity relationships: {len(config.entity_relationships)}")
            for r in config.entity_relationships:
                print(f"  - {r.from_entity}.{r.field_name} -> {r.to_entity} ({r.relation_type})")
    
    return config
