"""Generate subgraph.yaml file.

This module generates the subgraph.yaml manifest file that defines
data sources, event handlers, and mappings for the subgraph.
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.abi.utils import extract_events, get_handler_name, get_entity_name
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)


def _get_call_handler_name(function_signature: str) -> str:
    """Generate handler name for a call handler.
    
    Args:
        function_signature: Function signature like "transfer(address,uint256)".
    
    Returns:
        Handler name like "handleTransferCall".
    """
    # Extract function name from signature
    func_name = function_signature.split("(")[0].strip()
    # Capitalize first letter and add "Call" suffix
    return f"handle{func_name[0].upper()}{func_name[1:]}Call"


def _get_block_handler_name(contract_name: str) -> str:
    """Generate handler name for a block handler.
    
    Args:
        contract_name: Name of the contract.
    
    Returns:
        Handler name like "handleBlock".
    """
    return f"handle{contract_name}Block"


def _build_contract_context(
    contract: ContractConfig,
    abi: list[dict[str, Any]] | None = None,
    complexity: str = "basic",
) -> dict[str, Any]:
    """Build template context for a single contract.
    
    When ABI data is provided, event handlers are derived from events
    in the ABI. Otherwise, a placeholder handler is created.
    
    For intermediate complexity, call handlers and block handlers are
    included based on the contract configuration.
    
    Args:
        contract: Contract configuration.
        abi: Optional ABI data for the contract.
        complexity: Complexity level ('basic' or 'intermediate').
    
    Returns:
        Dictionary with contract data for template rendering.
    """
    # Extract event handlers and entity names from ABI
    if abi:
        events = extract_events(abi)
        if events:
            entities = [get_entity_name(event["name"]) for event in events]
            event_handlers = [
                {
                    "event_signature": event["signature"],
                    "handler_name": get_handler_name(event["name"]),
                }
                for event in events
            ]
        else:
            # No events found in ABI, use placeholder
            logger.warning(f"No events found in ABI for {contract.name}, using placeholder")
            entities = [f"{contract.name}Event"]
            event_handlers = [
                {
                    "event_signature": f"{contract.name}Event(address,uint256)",
                    "handler_name": f"handle{contract.name}Event",
                }
            ]
    else:
        # No ABI provided, use placeholder
        entities = [f"{contract.name}Event"]
        event_handlers = [
            {
                "event_signature": f"{contract.name}Event(address,uint256)",
                "handler_name": f"handle{contract.name}Event",
            }
        ]
    
    context = {
        "name": contract.name,
        "address": contract.address,
        "start_block": contract.start_block,
        "abi_path": contract.abi_path,
        "entities": entities,
        "event_handlers": event_handlers,
    }
    
    # Add intermediate complexity features
    if complexity == "intermediate":
        # Build call handlers context
        if contract.call_handlers:
            call_handlers = [
                {
                    "function_signature": sig,
                    "handler_name": _get_call_handler_name(sig),
                }
                for sig in contract.call_handlers
            ]
            context["call_handlers"] = call_handlers
            
            # Add entities for call handlers
            for sig in contract.call_handlers:
                func_name = sig.split("(")[0].strip()
                entity_name = f"{func_name[0].upper()}{func_name[1:]}Call"
                if entity_name not in entities:
                    entities.append(entity_name)
        
        # Build block handler context
        if contract.block_handler:
            context["block_handler"] = True
            context["block_handler_name"] = _get_block_handler_name(contract.name)
            
            # Add entity for block handler
            block_entity = f"{contract.name}Block"
            if block_entity not in entities:
                entities.append(block_entity)
    
    return context


def render_subgraph_yaml(
    config: SubgraphConfig,
    abi_map: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    """Render the subgraph.yaml manifest file.
    
    Generates a valid subgraph.yaml with data sources for each contract
    in the configuration. When ABI data is provided, event handlers are
    derived from events in the ABI.
    
    For intermediate complexity, call handlers and block handlers are
    included based on the contract configuration.
    
    Args:
        config: Subgraph configuration.
        abi_map: Optional mapping of contract names to their ABI data.
    
    Returns:
        Rendered subgraph.yaml content as a string.
    """
    logger.info(f"Rendering subgraph.yaml for {config.name}")
    logger.info(f"Complexity level: {config.complexity}")
    
    # Build contract contexts
    contracts_context = []
    for contract in config.contracts:
        abi = abi_map.get(contract.name) if abi_map else None
        contracts_context.append(_build_contract_context(contract, abi, config.complexity))
    
    context = {
        "subgraph_name": config.name,
        "network": config.network,
        "contracts": contracts_context,
    }
    
    return render_template("subgraph.yaml.j2", context)
