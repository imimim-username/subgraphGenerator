"""Generate GraphQL schema files.

This module generates schema.graphql files with entity types derived
from contract ABIs. In auto mode, each event in the ABI becomes an
entity type with fields for event parameters plus standard metadata.

For advanced complexity, this module also handles:
- Generating entities for template events
- Adding relationship fields between entities
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig, TemplateConfig, EntityRelationship
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


def _build_entities_from_template(
    template: TemplateConfig,
    abi: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build entity definitions from a template's events.
    
    Args:
        template: Template configuration.
        abi: Optional ABI data for the template.
    
    Returns:
        List of entity definitions for template rendering.
    """
    entities = []
    
    if abi:
        events = extract_events(abi)
        if events:
            # Filter to events specified in template.event_handlers
            filtered_events = [
                event for event in events
                if event["name"] in template.event_handlers
            ]
            for event in filtered_events:
                entity = _build_entity_from_event(event)
                entities.append(entity)
        else:
            # No events in ABI, use placeholder entities from event_handlers list
            for event_name in template.event_handlers:
                entities.append({
                    "name": get_entity_name(event_name),
                    "fields": [],
                })
    else:
        # No ABI, use placeholder entities from event_handlers list
        for event_name in template.event_handlers:
            entities.append({
                "name": get_entity_name(event_name),
                "fields": [],
            })
    
    return entities


def _add_relationship_fields(
    entities: list[dict[str, Any]],
    relationships: list[EntityRelationship],
) -> None:
    """Add relationship fields to entities based on EntityRelationship configs.
    
    Modifies entities in place to add reference fields and derived fields.
    
    Args:
        entities: List of entity definitions to modify.
        relationships: List of entity relationship configurations.
    """
    # Build a lookup map of entity names to entity definitions
    entity_map = {entity["name"]: entity for entity in entities}
    
    for relationship in relationships:
        from_entity = entity_map.get(relationship.from_entity)
        
        if from_entity is None:
            logger.warning(
                f"Entity '{relationship.from_entity}' not found for relationship "
                f"to '{relationship.to_entity}'. Skipping relationship field."
            )
            continue
        
        # Determine field type based on relation_type
        if relationship.relation_type == "one_to_one":
            field_type = relationship.to_entity
            required = False
        elif relationship.relation_type == "one_to_many":
            field_type = f"[{relationship.to_entity}!]!"
            required = False  # Arrays handle their own required semantics
        elif relationship.relation_type == "many_to_many":
            field_type = f"[{relationship.to_entity}!]!"
            required = False
        else:
            logger.warning(
                f"Unknown relation_type '{relationship.relation_type}' for relationship "
                f"from '{relationship.from_entity}' to '{relationship.to_entity}'. Using one_to_one."
            )
            field_type = relationship.to_entity
            required = False
        
        # Build the field definition
        field_def = {
            "name": relationship.field_name,
            "type": field_type,
            "required": required,
        }
        
        # Add derived field directive if specified
        if relationship.derived_from:
            field_def["derived_from"] = relationship.derived_from
        
        # Add the field to the entity
        from_entity["fields"].append(field_def)
        logger.debug(
            f"Added relationship field '{relationship.field_name}' to entity "
            f"'{relationship.from_entity}' referencing '{relationship.to_entity}'"
        )


def render_schema(
    config: SubgraphConfig,
    abi_map: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    """Render the schema.graphql file.
    
    Generates a GraphQL schema with entity types for each contract.
    When ABI data is provided, entities are derived from events in the ABI.
    Otherwise, placeholder entities are created for backward compatibility.
    
    For advanced complexity:
    - Generates entities for template events
    - Adds relationship fields between entities
    
    Args:
        config: Subgraph configuration.
        abi_map: Optional mapping of contract names to their ABI data.
                 For advanced complexity, should also include template ABIs.
    
    Returns:
        Rendered schema.graphql content as a string.
    """
    logger.info(f"Rendering schema.graphql for {config.name}")
    
    entities = []
    
    # Generate entities from contracts
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
    
    # Generate entities from templates (advanced complexity)
    if config.complexity == "advanced" and config.templates:
        for template in config.templates:
            abi = abi_map.get(template.name) if abi_map else None
            template_entities = _build_entities_from_template(template, abi)
            entities.extend(template_entities)
            logger.debug(f"Created {len(template_entities)} entities from template {template.name}")
    
    # Add relationship fields (advanced complexity)
    if config.complexity == "advanced" and config.entity_relationships:
        _add_relationship_fields(entities, config.entity_relationships)
        logger.info(f"Added {len(config.entity_relationships)} relationship fields to entities")
    
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
