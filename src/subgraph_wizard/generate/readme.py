"""Generate README files for subgraphs.

This module generates a README.md file for the subgraph project that
explains the subgraph configuration, how to build and deploy it, and
provides helpful getting-started information.
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.abi.utils import extract_events
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)


def _get_contract_events(
    contract: ContractConfig,
    abi: list[dict[str, Any]] | None,
) -> list[str]:
    """Get a list of event names for a contract.
    
    Args:
        contract: Contract configuration.
        abi: Optional ABI data for the contract.
    
    Returns:
        List of event names.
    """
    if abi:
        events = extract_events(abi)
        return [event["name"] for event in events]
    return []


def render_readme(
    config: SubgraphConfig,
    abi_map: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    """Render a README.md file for the subgraph project.
    
    Generates a comprehensive README that includes:
    - Subgraph overview (network, contracts)
    - Installation instructions
    - Build and deployment commands
    - Project structure documentation
    
    Args:
        config: Subgraph configuration.
        abi_map: Optional mapping of contract names to their ABI data.
    
    Returns:
        Rendered README content as a string.
    """
    logger.info(f"Rendering README for: {config.name}")
    
    # Build contract info with events
    contracts_info = []
    for contract in config.contracts:
        abi = abi_map.get(contract.name) if abi_map else None
        events = _get_contract_events(contract, abi)
        
        contracts_info.append({
            "name": contract.name,
            "address": contract.address,
            "start_block": contract.start_block,
            "abi_path": contract.abi_path,
            "events": events,
        })
    
    context: dict[str, Any] = {
        "name": config.name,
        "network": config.network,
        "complexity": config.complexity,
        "mappings_mode": config.mappings_mode,
        "contracts": contracts_info,
    }
    
    return render_template("README.generated.md.j2", context)
