"""Generate stub mapping files with TODOs.

This module generates TypeScript mapping files with stub handlers that
include TODO comments. When ABI data is provided, handlers are generated
for each event in the ABI with placeholder implementation code.
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.abi.utils import (
    extract_events,
    get_handler_name,
    get_entity_name,
    to_camel_case,
)
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)


def _build_imports_for_events(
    contract: ContractConfig,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build import statements for event types and entities.
    
    Args:
        contract: Contract configuration.
        events: List of event definitions.
    
    Returns:
        List of import definitions for template rendering.
    """
    imports = []
    
    # Import event types from generated contract types
    event_type_imports = [f"{event['name']} as {event['name']}Event" for event in events]
    if event_type_imports:
        imports.append({
            "types": event_type_imports,
            "from": f"../generated/{contract.name}/{contract.name}",
        })
    
    # Import entity types from generated schema
    entity_imports = [get_entity_name(event["name"]) for event in events]
    if entity_imports:
        imports.append({
            "types": entity_imports,
            "from": "../generated/schema",
        })
    
    return imports


def _build_imports_placeholder(contract: ContractConfig) -> list[dict[str, Any]]:
    """Build placeholder imports when ABI is not available.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        List of import definitions for template rendering.
    """
    return [
        {
            "types": [f"{contract.name}Event as {contract.name}EventEvent"],
            "from": f"../generated/{contract.name}/{contract.name}",
        },
        {
            "types": [f"{contract.name}Event"],
            "from": "../generated/schema",
        },
    ]


def _build_handler_for_event(event: dict[str, Any]) -> dict[str, Any]:
    """Build a handler definition for an event.
    
    Args:
        event: Event definition from ABI.
    
    Returns:
        Handler definition for template rendering.
    """
    handler_name = get_handler_name(event["name"])
    entity_name = get_entity_name(event["name"])
    event_type = f"{event['name']}Event"
    
    # Build parameter mappings
    params = []
    for param in event.get("params", []):
        params.append({
            "entity_field": to_camel_case(param["name"]),
            "event_param": param["name"],
        })
    
    return {
        "name": handler_name,
        "event_name": event["name"],
        "event_type": event_type,
        "entity_name": entity_name,
        "params": params,
    }


def _build_handler_placeholder(contract: ContractConfig) -> dict[str, Any]:
    """Build a placeholder handler when ABI is not available.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        Handler definition for template rendering.
    """
    return {
        "name": f"handle{contract.name}Event",
        "event_name": f"{contract.name}Event",
        "event_type": f"{contract.name}EventEvent",
        "entity_name": f"{contract.name}Event",
        "params": [
            {"entity_field": "sender", "event_param": "sender"},
            {"entity_field": "value", "event_param": "value"},
        ],
    }


def _build_mapping_header(
    contract: ContractConfig,
    network: str,
    imports: list[dict[str, Any]],
) -> str:
    """Build the common header section for a mapping file.
    
    Args:
        contract: Contract configuration.
        network: Network name.
        imports: List of import definitions.
    
    Returns:
        Rendered header content as a string.
    """
    context = {
        "contract_name": contract.name,
        "network": network,
        "imports": imports,
    }
    
    return render_template("mappings/common_header.ts.j2", context)


def _build_call_handler_context(
    contract: ContractConfig,
    function_signature: str,
) -> dict[str, Any]:
    """Build context for a call handler.
    
    Args:
        contract: Contract configuration.
        function_signature: Function signature like "transfer(address,uint256)".
    
    Returns:
        Handler context for template rendering.
    """
    func_name = function_signature.split("(")[0].strip()
    handler_name = f"handle{func_name[0].upper()}{func_name[1:]}Call"
    entity_name = f"{func_name[0].upper()}{func_name[1:]}Call"
    call_type = f"{func_name[0].upper()}{func_name[1:]}Call"
    
    return {
        "name": handler_name,
        "function_name": func_name,
        "call_type": call_type,
        "entity_name": entity_name,
        "inputs": [],  # Can be populated from ABI if needed
        "outputs": [],
    }


def _build_block_handler_context(contract: ContractConfig) -> dict[str, Any]:
    """Build context for a block handler.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        Block handler context for template rendering.
    """
    return {
        "name": f"handle{contract.name}Block",
        "contract_name": contract.name,
        "entity_name": f"{contract.name}Block",
    }


def render_mapping_stub(
    contract: ContractConfig,
    network: str,
    abi: list[dict[str, Any]] | None = None,
    complexity: str = "basic",
) -> str:
    """Render a stub mapping file for a contract.
    
    Generates a TypeScript mapping file with stub event handlers that
    include TODO comments showing how to implement entity storage.
    When ABI data is provided, handlers are generated for each event.
    
    For intermediate complexity, call handlers and block handlers are
    included based on the contract configuration.
    
    Args:
        contract: Contract configuration.
        network: Network name.
        abi: Optional ABI data for the contract.
        complexity: Complexity level ('basic' or 'intermediate').
    
    Returns:
        Rendered mapping file content as a string.
    """
    logger.info(f"Rendering stub mapping for contract: {contract.name}")
    
    # Extract events from ABI or use placeholders
    if abi:
        events = extract_events(abi)
        if events:
            imports = _build_imports_for_events(contract, events)
            handlers = [_build_handler_for_event(event) for event in events]
        else:
            logger.warning(f"No events found in ABI for {contract.name}, using placeholder")
            imports = _build_imports_placeholder(contract)
            handlers = [_build_handler_placeholder(contract)]
    else:
        logger.debug(f"No ABI provided for {contract.name}, using placeholder")
        imports = _build_imports_placeholder(contract)
        handlers = [_build_handler_placeholder(contract)]
    
    # Build the header
    header = _build_mapping_header(contract, network, imports)
    
    context = {
        "header": header,
        "handlers": handlers,
    }
    
    # Add intermediate complexity features
    if complexity == "intermediate":
        # Add call handlers if configured
        if contract.call_handlers:
            call_handlers = [
                _build_call_handler_context(contract, sig)
                for sig in contract.call_handlers
            ]
            context["call_handlers"] = call_handlers
        
        # Add block handler if configured
        if contract.block_handler:
            context["block_handler"] = _build_block_handler_context(contract)
    
    return render_template("mappings/mapping_stub.ts.j2", context)


def render_all_mappings_stub(
    config: SubgraphConfig,
    abi_map: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, str]:
    """Render stub mapping files for all contracts.
    
    Args:
        config: Subgraph configuration.
        abi_map: Optional mapping of contract names to their ABI data.
    
    Returns:
        Dictionary mapping contract names to rendered mapping content.
    """
    logger.info(f"Rendering stub mappings for {len(config.contracts)} contracts")
    logger.info(f"Complexity level: {config.complexity}")
    
    result = {}
    for contract in config.contracts:
        abi = abi_map.get(contract.name) if abi_map else None
        result[contract.name] = render_mapping_stub(
            contract, config.network, abi, config.complexity
        )
    
    return result


def get_all_handlers_for_contract(
    contract: ContractConfig,
    abi: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Get all event handler definitions for a contract.
    
    This is useful for building subgraph.yaml which needs to list all
    event handlers for each data source.
    
    Args:
        contract: Contract configuration.
        abi: Optional ABI data for the contract.
    
    Returns:
        List of handler definitions with event_signature and handler_name.
    """
    if abi:
        events = extract_events(abi)
        if events:
            return [
                {
                    "event_signature": event["signature"],
                    "handler_name": get_handler_name(event["name"]),
                }
                for event in events
            ]
    
    # Fallback to placeholder handler
    return [
        {
            "event_signature": f"{contract.name}Event(address,uint256)",
            "handler_name": f"handle{contract.name}Event",
        }
    ]
