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

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
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
        complexity: Complexity level ('basic' or 'intermediate').
    
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
    
    # Collect intermediate complexity options if applicable
    if complexity == "intermediate":
        print("\n--- Intermediate Complexity Options ---")
        
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
    complexity = ask_choice(
        "Select complexity level",
        ["basic", "intermediate"],
        default_index=0
    )
    
    if complexity == "intermediate":
        print("\n📋 Intermediate mode enabled!")
        print("   You can configure call handlers and block handlers for each contract.")
    
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
    
    # Expand ~ to user's home directory before building config
    output_path = Path(output_dir).expanduser()
    expanded_output_dir = str(output_path)
    
    # Determine config version based on complexity
    config_version = 2 if complexity == "intermediate" else 1
    
    # Build the config
    config = SubgraphConfig(
        name=subgraph_name,
        network=network,
        output_dir=expanded_output_dir,
        mappings_mode=mapping_mode,
        contracts=contracts,
        config_version=config_version,
        complexity=complexity
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
    
    # Show intermediate features summary
    if config.complexity == "intermediate":
        contracts_with_call = [c.name for c in config.contracts if c.call_handlers]
        contracts_with_block = [c.name for c in config.contracts if c.block_handler]
        
        if contracts_with_call:
            print(f"\nContracts with call handlers: {', '.join(contracts_with_call)}")
        if contracts_with_block:
            print(f"Contracts with block handlers: {', '.join(contracts_with_block)}")
    
    return config
