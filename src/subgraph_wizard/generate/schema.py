"""Generate GraphQL schema files."""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)


def _build_entity_for_contract(contract: ContractConfig) -> dict[str, Any]:
    """Build a placeholder entity for a contract.
    
    For the MVP, creates a single ExampleEntity per contract with
    fixed fields. This will be replaced with actual ABI-derived
    event entities once ABI parsing is connected.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        Dictionary describing the entity for template rendering.
    """
    # MVP: placeholder entity with basic fields
    # Will be replaced with actual event-based entities in Milestone 4
    return {
        "name": f"{contract.name}Event",
        "fields": [
            {"name": "sender", "type": "Bytes", "required": True},
            {"name": "value", "type": "BigInt", "required": True},
        ],
    }


def render_schema(config: SubgraphConfig) -> str:
    """Render the schema.graphql file.
    
    Generates a GraphQL schema with entity types for each contract.
    For the MVP, creates placeholder entities that will be enhanced
    once ABI parsing is connected.
    
    Args:
        config: Subgraph configuration.
    
    Returns:
        Rendered schema.graphql content as a string.
    """
    logger.info(f"Rendering schema.graphql for {config.name}")
    
    # Build entity definitions for each contract
    entities = [
        _build_entity_for_contract(contract)
        for contract in config.contracts
    ]
    
    context = {
        "subgraph_name": config.name,
        "network": config.network,
        "entities": entities,
    }
    
    return render_template("schema/base_schema.graphql.j2", context)
