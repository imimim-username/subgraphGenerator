"""Generate auto-complete mapping files.

This module generates TypeScript mapping files that automatically create
and populate entities from event parameters. When ABI data is provided,
handlers are generated for each event in the ABI.

For advanced complexity, this module also handles:
- Template instantiation code in factory contract event handlers
- Generating separate mapping files for dynamic data source templates
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig, TemplateConfig
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
    templates: list[TemplateConfig] | None = None,
) -> list[dict[str, Any]]:
    """Build import statements for event types and entities.
    
    For advanced complexity, also includes imports for templates that
    this contract instantiates.
    
    Args:
        contract: Contract configuration.
        events: List of event definitions.
        templates: Optional list of templates instantiated by this contract.
    
    Returns:
        List of import definitions for template rendering.
    """
    imports = []
    
    # Import event types from generated contract types
    event_type_imports = [f"{event['name']} as {event['name']}Event" for event in events]
    if event_type_imports:
        imports.append({
            "types": event_type_imports,
            "from": f"../../generated/{contract.name}/{contract.name}",
        })
    
    # Import entity types from generated schema
    entity_imports = [get_entity_name(event["name"]) for event in events]
    if entity_imports:
        imports.append({
            "types": entity_imports,
            "from": "../../generated/schema",
        })
    
    # Import template types for advanced complexity
    if templates:
        template_imports = [t.name for t in templates if t.source_contract == contract.name]
        if template_imports:
            imports.append({
                "types": template_imports,
                "from": "../../generated/templates",
            })
    
    return imports


def _build_imports_placeholder(
    contract: ContractConfig,
    templates: list[TemplateConfig] | None = None,
) -> list[dict[str, Any]]:
    """Build placeholder imports when ABI is not available.
    
    Args:
        contract: Contract configuration.
        templates: Optional list of templates instantiated by this contract.
    
    Returns:
        List of import definitions for template rendering.
    """
    imports = [
        {
            "types": [f"{contract.name}Event as {contract.name}EventEvent"],
            "from": f"../../generated/{contract.name}/{contract.name}",
        },
        {
            "types": [f"{contract.name}Event"],
            "from": "../../generated/schema",
        },
    ]
    
    # Import template types for advanced complexity
    if templates:
        template_imports = [t.name for t in templates if t.source_contract == contract.name]
        if template_imports:
            imports.append({
                "types": template_imports,
                "from": "../../generated/templates",
            })
    
    return imports


def _build_handler_for_event(
    event: dict[str, Any],
    templates: list[TemplateConfig] | None = None,
    contract_name: str | None = None,
) -> dict[str, Any]:
    """Build a handler definition for an event.
    
    For advanced complexity, if this event triggers template instantiation,
    the handler will include template creation code.
    
    Args:
        event: Event definition from ABI.
        templates: Optional list of templates that may be triggered by this event.
        contract_name: Name of the contract (needed to match templates).
    
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
    
    handler = {
        "name": handler_name,
        "event_type": event_type,
        "entity_name": entity_name,
        "params": params,
    }
    
    # Check if this event triggers any template instantiation (advanced complexity)
    if templates and contract_name:
        for template in templates:
            if template.source_contract == contract_name and template.source_event == event["name"]:
                # Find the address parameter (commonly named 'pair', 'pool', 'token', etc.)
                # For now, use the first address parameter or fall back to a common pattern
                address_param = None
                for param in event.get("params", []):
                    if param.get("type") == "address" and not param.get("indexed", False):
                        address_param = param["name"]
                        break
                    elif param.get("type") == "address":
                        address_param = param["name"]
                
                if address_param:
                    handler["template_creation"] = {
                        "template_name": template.name,
                        "address_param": address_param,
                    }
                else:
                    logger.warning(
                        f"Template {template.name} triggered by {event['name']} but no address "
                        f"parameter found. Template creation code will need manual adjustment."
                    )
                    handler["template_creation"] = {
                        "template_name": template.name,
                        "address_param": "ADDRESS_PARAM_HERE",  # Placeholder
                    }
                break  # One event can only instantiate one template
    
    return handler


def _build_handler_placeholder(contract: ContractConfig) -> dict[str, Any]:
    """Build a placeholder handler when ABI is not available.
    
    Args:
        contract: Contract configuration.
    
    Returns:
        Handler definition for template rendering.
    """
    return {
        "name": f"handle{contract.name}Event",
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


def render_mapping_auto(
    contract: ContractConfig,
    network: str,
    abi: list[dict[str, Any]] | None = None,
    complexity: str = "basic",
    templates: list[TemplateConfig] | None = None,
) -> str:
    """Render an auto-generated mapping file for a contract.
    
    Generates a TypeScript mapping file with event handlers that
    automatically create and populate entities from event parameters.
    When ABI data is provided, handlers are generated for each event.
    
    For intermediate complexity, call handlers and block handlers are
    included based on the contract configuration.
    
    For advanced complexity, template instantiation code is included
    in event handlers that trigger template creation.
    
    Args:
        contract: Contract configuration.
        network: Network name.
        abi: Optional ABI data for the contract.
        complexity: Complexity level ('basic', 'intermediate', or 'advanced').
        templates: Optional list of templates (for advanced complexity).
    
    Returns:
        Rendered mapping file content as a string.
    """
    logger.info(f"Rendering auto mapping for contract: {contract.name}")
    
    # Get templates that this contract instantiates (for advanced complexity)
    contract_templates = None
    if complexity == "advanced" and templates:
        contract_templates = [t for t in templates if t.source_contract == contract.name]
    
    # Extract events from ABI or use placeholders
    if abi:
        events = extract_events(abi)
        if events:
            imports = _build_imports_for_events(contract, events, contract_templates)
            handlers = [
                _build_handler_for_event(event, contract_templates, contract.name)
                for event in events
            ]
        else:
            logger.warning(f"No events found in ABI for {contract.name}, using placeholder")
            imports = _build_imports_placeholder(contract, contract_templates)
            handlers = [_build_handler_placeholder(contract)]
    else:
        logger.debug(f"No ABI provided for {contract.name}, using placeholder")
        imports = _build_imports_placeholder(contract, contract_templates)
        handlers = [_build_handler_placeholder(contract)]
    
    # Build the header
    header = _build_mapping_header(contract, network, imports)
    
    context = {
        "header": header,
        "handlers": handlers,
    }
    
    # Add intermediate/advanced complexity features
    if complexity in ("intermediate", "advanced"):
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
    
    return render_template("mappings/mapping_auto.ts.j2", context)


def render_all_mappings_auto(
    config: SubgraphConfig,
    abi_map: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, str]:
    """Render auto-generated mapping files for all contracts.
    
    For advanced complexity, this also generates mapping files for templates.
    
    Args:
        config: Subgraph configuration.
        abi_map: Optional mapping of contract names to their ABI data.
                 For advanced complexity, should also include template ABIs.
    
    Returns:
        Dictionary mapping contract/template names to rendered mapping content.
    """
    logger.info(f"Rendering auto mappings for {len(config.contracts)} contracts")
    logger.info(f"Complexity level: {config.complexity}")
    
    result = {}
    
    # Get templates for advanced complexity
    templates = config.templates if config.complexity == "advanced" else None
    
    # Render contract mappings
    for contract in config.contracts:
        abi = abi_map.get(contract.name) if abi_map else None
        result[contract.name] = render_mapping_auto(
            contract, config.network, abi, config.complexity, templates
        )
    
    # Render template mappings for advanced complexity
    if config.complexity == "advanced" and config.templates:
        for template in config.templates:
            abi = abi_map.get(template.name) if abi_map else None
            result[template.name] = render_template_mapping_auto(
                template, config.network, abi
            )
        logger.info(f"Rendered mappings for {len(config.templates)} template(s)")
    
    return result


def render_template_mapping_auto(
    template: TemplateConfig,
    network: str,
    abi: list[dict[str, Any]] | None = None,
) -> str:
    """Render an auto-generated mapping file for a template.
    
    Similar to contract mappings, but for dynamic data source templates.
    These are instantiated at runtime by factory contracts.
    
    Args:
        template: Template configuration.
        network: Network name.
        abi: Optional ABI data for the template.
    
    Returns:
        Rendered mapping file content as a string.
    """
    logger.info(f"Rendering auto mapping for template: {template.name}")
    
    # Extract events from ABI, filtered to template.event_handlers
    imports = []
    handlers = []
    
    if abi:
        events = extract_events(abi)
        if events:
            # Filter events to only those specified in template.event_handlers
            filtered_events = [
                event for event in events
                if event["name"] in template.event_handlers
            ]
            if filtered_events:
                # Import event types
                event_type_imports = [
                    f"{event['name']} as {event['name']}Event"
                    for event in filtered_events
                ]
                imports.append({
                    "types": event_type_imports,
                    "from": f"../../generated/templates/{template.name}/{template.name}",
                })
                
                # Import entity types
                entity_imports = [get_entity_name(event["name"]) for event in filtered_events]
                imports.append({
                    "types": entity_imports,
                    "from": "../../generated/schema",
                })
                
                # Build handlers
                handlers = [_build_handler_for_event(event) for event in filtered_events]
            else:
                logger.warning(f"No events in ABI match template event_handlers for {template.name}")
                # Use placeholder based on event_handlers list
                imports, handlers = _build_template_placeholders(template)
        else:
            logger.warning(f"No events found in ABI for template {template.name}")
            imports, handlers = _build_template_placeholders(template)
    else:
        logger.debug(f"No ABI provided for template {template.name}")
        imports, handlers = _build_template_placeholders(template)
    
    # Build header context
    header_context = {
        "contract_name": template.name,
        "network": network,
        "imports": imports,
    }
    header = render_template("mappings/common_header.ts.j2", header_context)
    
    context = {
        "header": header,
        "handlers": handlers,
    }
    
    # Add call handlers if configured
    if template.call_handlers:
        call_handlers = []
        for sig in template.call_handlers:
            func_name = sig.split("(")[0].strip()
            handler_name = f"handle{func_name[0].upper()}{func_name[1:]}Call"
            entity_name = f"{func_name[0].upper()}{func_name[1:]}Call"
            call_type = f"{func_name[0].upper()}{func_name[1:]}Call"
            call_handlers.append({
                "name": handler_name,
                "function_name": func_name,
                "call_type": call_type,
                "entity_name": entity_name,
                "inputs": [],
                "outputs": [],
            })
        context["call_handlers"] = call_handlers
    
    # Add block handler if configured
    if template.block_handler:
        context["block_handler"] = {
            "name": f"handle{template.name}Block",
            "contract_name": template.name,
            "entity_name": f"{template.name}Block",
        }
    
    return render_template("mappings/mapping_auto.ts.j2", context)


def _build_template_placeholders(
    template: TemplateConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build placeholder imports and handlers for a template.
    
    Args:
        template: Template configuration.
    
    Returns:
        Tuple of (imports list, handlers list).
    """
    imports = []
    handlers = []
    
    # Build event type imports
    event_type_imports = [
        f"{name} as {name}Event"
        for name in template.event_handlers
    ]
    if event_type_imports:
        imports.append({
            "types": event_type_imports,
            "from": f"../../generated/templates/{template.name}/{template.name}",
        })
    
    # Build entity imports
    entity_imports = [get_entity_name(name) for name in template.event_handlers]
    if entity_imports:
        imports.append({
            "types": entity_imports,
            "from": "../../generated/schema",
        })
    
    # Build placeholder handlers
    for name in template.event_handlers:
        handlers.append({
            "name": get_handler_name(name),
            "event_type": f"{name}Event",
            "entity_name": get_entity_name(name),
            "params": [],  # No params for placeholders
        })
    
    return imports, handlers


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
