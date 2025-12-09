"""Generate GraphQL schema files.

This module generates schema.graphql files with entity types derived
from contract ABIs. In auto mode, each event in the ABI becomes an
entity type with fields for event parameters plus standard metadata.
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.abi.utils import extract_events, get_entity_name, to_camel_case
from subgraph_wizard.utils.templating import render_template

logger = logging.getLogger(__name__)


def _build_entity_from_event(event: dict[str, Any]) -> dict[str, Any]:
    """Build an entity definition from an event.
    
    Creates a GraphQL entity type with fields corresponding to the event's
    parameters, plus standard metadata fields (blockNumber, timestamp, etc).
    
    Args:
        event: Event definition from ABI (with name and params).
    
    Returns:
        Dictionary describing the entity for template rendering.
    """
    entity_name = get_entity_name(event["name"])
    
    # Build fields from event parameters
    fields = []
    for param in event.get("params", []):
        field_name = to_camel_case(param["name"])
        graph_type = param["graph_type"]
        
        fields.append({
            "name": field_name,
            "type": graph_type,
            "required": True,
        })
    
    return {
        "name": entity_name,
        "fields": fields,
    }


def _build_entity_for_contract_placeholder(contract: ContractConfig) -> dict[str, Any]:
    """Build a placeholder entity for a contract (fallback when no ABI).
    
    For backward compatibility, creates a single placeholder entity per
    contract when ABI is not provided.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        Dictionary describing the entity for template rendering.
    """
    return {
        "name": f"{contract.name}Event",
        "fields": [
            {"name": "sender", "type": "Bytes", "required": True},
            {"name": "value", "type": "BigInt", "required": True},
        ],
    }


def render_schema(
    config: SubgraphConfig,
    abi_map: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    """Render the schema.graphql file.
    
    Generates a GraphQL schema with entity types for each contract.
    When ABI data is provided, entities are derived from events in the ABI.
    Otherwise, placeholder entities are created for backward compatibility.
    
    Args:
        config: Subgraph configuration.
        abi_map: Optional mapping of contract names to their ABI data.
                 If not provided, placeholder entities are generated.
    
    Returns:
        Rendered schema.graphql content as a string.
    """
    logger.info(f"Rendering schema.graphql for {config.name}")
    
    entities = []
    
    for contract in config.contracts:
        if abi_map and contract.name in abi_map:
            # Generate entities from ABI events
            abi = abi_map[contract.name]
            events = extract_events(abi)
            
            if events:
                for event in events:
                    entity = _build_entity_from_event(event)
                    entities.append(entity)
                    logger.debug(f"Created entity {entity['name']} from event {event['name']}")
            else:
                # No events found, use placeholder
                logger.warning(f"No events found in ABI for {contract.name}, using placeholder entity")
                entities.append(_build_entity_for_contract_placeholder(contract))
        else:
            # No ABI provided, use placeholder
            logger.debug(f"No ABI provided for {contract.name}, using placeholder entity")
            entities.append(_build_entity_for_contract_placeholder(contract))
    
    context = {
        "subgraph_name": config.name,
        "network": config.network,
        "entities": entities,
    }
    
    return render_template("schema/base_schema.graphql.j2", context)


def get_all_entities_for_contract(
    contract: ContractConfig,
    abi: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Get all entity names that will be generated for a contract.
    
    This is useful for building subgraph.yaml which needs to list all
    entities for each data source.
    
    Args:
        contract: Contract configuration.
        abi: Optional ABI data for the contract.
    
    Returns:
        List of entity names.
    """
    if abi:
        events = extract_events(abi)
        if events:
            return [get_entity_name(event["name"]) for event in events]
    
    # Fallback to placeholder entity
    return [f"{contract.name}Event"]
