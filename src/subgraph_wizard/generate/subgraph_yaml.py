"""Generate subgraph.yaml file."""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)


def _build_contract_context(contract: ContractConfig) -> dict[str, Any]:
    """Build template context for a single contract.
    
    For the MVP, we generate a single placeholder event handler per contract.
    This will be enhanced once ABI parsing is connected.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        Dictionary with contract data for template rendering.
    """
    # For MVP: single placeholder entity and handler
    # Will be replaced with actual ABI-derived events in Milestone 4
    entity_name = f"{contract.name}Event"
    handler_name = f"handle{contract.name}Event"
    event_signature = f"{contract.name}Event(address,uint256)"
    
    return {
        "name": contract.name,
        "address": contract.address,
        "start_block": contract.start_block,
        "abi_path": contract.abi_path,
        "entities": [entity_name],
        "event_handlers": [
            {
                "event_signature": event_signature,
                "handler_name": handler_name,
            }
        ],
    }


def render_subgraph_yaml(config: SubgraphConfig) -> str:
    """Render the subgraph.yaml manifest file.
    
    Generates a valid subgraph.yaml with data sources for each contract
    in the configuration. For the MVP, uses placeholder event handlers
    that will be enhanced once ABI parsing is connected.
    
    Args:
        config: Subgraph configuration.
    
    Returns:
        Rendered subgraph.yaml content as a string.
    """
    logger.info(f"Rendering subgraph.yaml for {config.name}")
    
    # Build contract contexts
    contracts_context = [
        _build_contract_context(contract)
        for contract in config.contracts
    ]
    
    context = {
        "subgraph_name": config.name,
        "network": config.network,
        "contracts": contracts_context,
    }
    
    return render_template("subgraph.yaml.j2", context)
