"""Generate auto-complete mapping files."""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)


def _build_mapping_header(contract: ContractConfig, network: str) -> str:
    """Build the common header section for a mapping file.
    
    Args:
        contract: Contract configuration.
        network: Network name.
    
    Returns:
        Rendered header content as a string.
    """
    # Import statements for the generated types
    # For MVP: placeholder imports that match the placeholder entities
    imports = [
        {
            "types": [f"{contract.name}Event as {contract.name}EventEvent"],
            "from": f"../generated/{contract.name}/{contract.name}",
        },
        {
            "types": [f"{contract.name}Event"],
            "from": "../generated/schema",
        },
    ]
    
    context = {
        "contract_name": contract.name,
        "network": network,
        "imports": imports,
    }
    
    return render_template("mappings/common_header.ts.j2", context)


def _build_mapping_handlers(contract: ContractConfig) -> list[dict[str, Any]]:
    """Build handler definitions for a contract's mapping file.
    
    For the MVP, creates a single placeholder handler per contract.
    This will be enhanced with actual ABI-derived event handlers.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        List of handler definitions for template rendering.
    """
    # MVP: single placeholder handler
    # Will be replaced with actual event handlers in Milestone 4
    return [
        {
            "name": f"handle{contract.name}Event",
            "event_type": f"{contract.name}EventEvent",
            "entity_name": f"{contract.name}Event",
            "params": [
                {"entity_field": "sender", "event_param": "sender"},
                {"entity_field": "value", "event_param": "value"},
            ],
        }
    ]


def render_mapping_auto(contract: ContractConfig, network: str) -> str:
    """Render an auto-generated mapping file for a contract.
    
    Generates a TypeScript mapping file with event handlers that
    automatically create and populate entities from event parameters.
    
    Args:
        contract: Contract configuration.
        network: Network name.
    
    Returns:
        Rendered mapping file content as a string.
    """
    logger.info(f"Rendering auto mapping for contract: {contract.name}")
    
    # Build the header
    header = _build_mapping_header(contract, network)
    
    # Build handlers
    handlers = _build_mapping_handlers(contract)
    
    context = {
        "header": header,
        "handlers": handlers,
    }
    
    return render_template("mappings/mapping_auto.ts.j2", context)


def render_all_mappings_auto(config: SubgraphConfig) -> dict[str, str]:
    """Render auto-generated mapping files for all contracts.
    
    Args:
        config: Subgraph configuration.
    
    Returns:
        Dictionary mapping contract names to rendered mapping content.
    """
    logger.info(f"Rendering auto mappings for {len(config.contracts)} contracts")
    
    return {
        contract.name: render_mapping_auto(contract, config.network)
        for contract in config.contracts
    }
