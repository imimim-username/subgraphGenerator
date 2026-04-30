"""Generate subgraph.yaml file.

This module contains two distinct renderers:

1. render_subgraph_yaml() — existing pipeline; uses SubgraphConfig with
   hardcoded addresses. Unchanged.

2. render_visual_subgraph_yaml() — NEW; generates a mustache-templated
   subgraph.yaml from the visual editor's graph state. Addresses are
   replaced with {{DataSourceName.address}} placeholders so that
   `graph build --network <name>` can substitute values from networks.json.


This module generates the subgraph.yaml manifest file that defines
data sources, event handlers, and mappings for the subgraph.

For advanced complexity, this module also handles:
- Dynamic data source templates for factory-created contracts
- Template instantiation via factory events
"""

import logging
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig, TemplateConfig
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
    templates: list[TemplateConfig] | None = None,
) -> dict[str, Any]:
    """Build template context for a single contract.
    
    When ABI data is provided, event handlers are derived from events
    in the ABI. Otherwise, a placeholder handler is created.
    
    For intermediate complexity, call handlers and block handlers are
    included based on the contract configuration.
    
    For advanced complexity, this also identifies template ABIs that need
    to be included in the contract's mapping file for template instantiation.
    
    Args:
        contract: Contract configuration.
        abi: Optional ABI data for the contract.
        complexity: Complexity level ('basic', 'intermediate', or 'advanced').
        templates: List of templates that may be instantiated by this contract.
    
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
    if complexity in ("intermediate", "advanced"):
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
    
    # Add advanced complexity features - template ABIs
    if complexity == "advanced" and templates:
        template_abis = []
        for template in templates:
            if template.source_contract == contract.name:
                template_abis.append({
                    "name": template.name,
                    "path": template.abi_path,
                })
        if template_abis:
            context["template_abis"] = template_abis
    
    return context


def _build_template_context(
    template: TemplateConfig,
    abi: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build template context for a dynamic data source template.
    
    When ABI data is provided, event handlers are derived from events
    in the ABI that match the template's event_handlers list.
    
    Args:
        template: Template configuration.
        abi: Optional ABI data for the template.
    
    Returns:
        Dictionary with template data for Jinja2 rendering.
    """
    # Extract event handlers and entity names from ABI
    if abi:
        events = extract_events(abi)
        # Filter events to only those specified in template.event_handlers
        if events:
            filtered_events = [
                event for event in events
                if event["name"] in template.event_handlers
            ]
            if filtered_events:
                entities = [get_entity_name(event["name"]) for event in filtered_events]
                event_handlers = [
                    {
                        "event_signature": event["signature"],
                        "handler_name": get_handler_name(event["name"]),
                    }
                    for event in filtered_events
                ]
            else:
                # No matching events found, create handlers from names
                logger.warning(
                    f"No events in ABI match template event_handlers for {template.name}"
                )
                entities = [get_entity_name(name) for name in template.event_handlers]
                event_handlers = [
                    {
                        "event_signature": f"{name}()",
                        "handler_name": get_handler_name(name),
                    }
                    for name in template.event_handlers
                ]
        else:
            # No events in ABI, use template's event_handlers list
            logger.warning(f"No events found in ABI for template {template.name}")
            entities = [get_entity_name(name) for name in template.event_handlers]
            event_handlers = [
                {
                    "event_signature": f"{name}()",
                    "handler_name": get_handler_name(name),
                }
                for name in template.event_handlers
            ]
    else:
        # No ABI provided, use template's event_handlers list
        entities = [get_entity_name(name) for name in template.event_handlers]
        event_handlers = [
            {
                "event_signature": f"{name}()",
                "handler_name": get_handler_name(name),
            }
            for name in template.event_handlers
        ]
    
    context = {
        "name": template.name,
        "abi_path": template.abi_path,
        "entities": entities,
        "event_handlers": event_handlers,
        "source_contract": template.source_contract,
        "source_event": template.source_event,
    }
    
    # Add call handlers if configured
    if template.call_handlers:
        call_handlers = [
            {
                "function_signature": sig,
                "handler_name": _get_call_handler_name(sig),
            }
            for sig in template.call_handlers
        ]
        context["call_handlers"] = call_handlers
        
        # Add entities for call handlers
        for sig in template.call_handlers:
            func_name = sig.split("(")[0].strip()
            entity_name = f"{func_name[0].upper()}{func_name[1:]}Call"
            if entity_name not in entities:
                entities.append(entity_name)
    
    # Add block handler if configured
    if template.block_handler:
        context["block_handler"] = True
        context["block_handler_name"] = _get_block_handler_name(template.name)
        
        # Add entity for block handler
        block_entity = f"{template.name}Block"
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
    
    For advanced complexity, templates for dynamic data sources are
    included based on the config's templates list.
    
    Args:
        config: Subgraph configuration.
        abi_map: Optional mapping of contract names to their ABI data.
                 For advanced complexity, this should also include template ABIs.
    
    Returns:
        Rendered subgraph.yaml content as a string.
    """
    logger.info(f"Rendering subgraph.yaml for {config.name}")
    logger.info(f"Complexity level: {config.complexity}")
    
    # Build contract contexts
    contracts_context = []
    templates_for_contracts = config.templates if config.complexity == "advanced" else None
    for contract in config.contracts:
        abi = abi_map.get(contract.name) if abi_map else None
        contracts_context.append(
            _build_contract_context(contract, abi, config.complexity, templates_for_contracts)
        )
    
    context = {
        "subgraph_name": config.name,
        "network": config.network,
        "contracts": contracts_context,
    }
    
    # Add templates for advanced complexity
    if config.complexity == "advanced" and config.templates:
        templates_context = []
        for template in config.templates:
            abi = abi_map.get(template.name) if abi_map else None
            templates_context.append(_build_template_context(template, abi))
        context["templates"] = templates_context
        logger.info(f"Including {len(templates_context)} template(s) for dynamic data sources")
    
    return render_template("subgraph.yaml.j2", context)


# ── Visual editor renderer ────────────────────────────────────────────────────

def render_visual_subgraph_yaml(
    visual_config: dict[str, Any],
    first_network: str = "mainnet",
) -> str:
    """Render a mustache-templated subgraph.yaml from a visual graph config.

    The generated file uses ``{{DataSourceName.address}}`` and
    ``{{DataSourceName.startBlock}}`` placeholders that graph-cli substitutes
    from ``networks.json`` at build time (``graph build --network <name>``).

    One data source block is emitted per contract instance (ContractType_label).
    All instances of the same contract type share the same ABI file and handler
    file but get their own named data source.

    Only events that the compiler actually generates handler functions for are
    included in ``eventHandlers``.  Including a handler that doesn't exist in
    the mapping file causes ``graph build`` to fail.

    Args:
        visual_config: Parsed visual-config.json dict.
        first_network: Network name to embed in the YAML's ``network:`` field.
            Defaults to "mainnet"; graph-cli substitutes the real network at
            deploy time, but the field must be present.

    Returns:
        Rendered subgraph.yaml content as a string.
    """
    from subgraph_wizard.generate.graph_compiler import GraphCompiler, build_entity_name_map

    nodes = visual_config.get("nodes", [])
    edges = visual_config.get("edges", [])
    networks_config: list[dict[str, Any]] = visual_config.get("networks", [])

    # Compile to determine which events actually have generated handler functions.
    # Including a handler name in subgraph.yaml that doesn't exist in the mapping
    # file causes `graph build` to fail with "handler not found".
    compiler = GraphCompiler(visual_config)
    compiled_outputs = compiler.compile()
    # {contract_type: set of event_names with handlers}
    handled_events: dict[str, set[str]] = {
        ct: {h.event_name for h in out.handlers}
        for ct, out in compiled_outputs.items()
    }

    # Collect contract nodes indexed by id
    contract_nodes: dict[str, dict[str, Any]] = {
        n["id"]: n["data"]
        for n in nodes
        if n.get("type") == "contract"
    }

    # Collect resolved entity names (deduplicated, contract-prefixed where needed)
    name_map = build_entity_name_map(nodes, edges)
    entity_names: list[str] = sorted(set(name_map.values()))

    # Build a per-contract-type instance lookup from the Networks tab config.
    # Structure: networks[i] = {"network": "mainnet", "contracts": {ContractType: {"instances": [...]}}}
    # Prefer the entry matching first_network; fall back to the first entry.
    network_instances: dict[str, list[dict[str, Any]]] = {}
    resolved_network: str = first_network
    if networks_config:
        network_entry = next(
            (n for n in networks_config if n.get("network") == first_network),
            networks_config[0],
        )
        resolved_network = network_entry.get("network", first_network)
        for ct, ct_info in network_entry.get("contracts", {}).items():
            insts = ct_info.get("instances", [])
            if insts:
                network_instances[ct] = insts

    data_sources: list[dict[str, Any]] = []

    for contract_id, contract_data in contract_nodes.items():
        contract_type = contract_data.get("name", "")
        if not contract_type:
            logger.warning(f"Contract node {contract_id} has no name — skipping")
            continue

        events = contract_data.get("events", [])
        abi_path = f"{contract_type}.json"

        # Only include events that have generated handler functions in the mapping.
        ct_handled = handled_events.get(contract_type, set())
        event_handlers = [
            {
                "event_signature": ev.get("signature", f'{ev["name"]}()'),
                "handler_name": get_handler_name(ev["name"]),
            }
            for ev in events
            if ev.get("name") in ct_handled
        ]

        # Prefer instances from the Networks tab (authoritative for addresses/startBlocks).
        # Fall back to instances stored on the node, then to a single unlabelled instance.
        if contract_type in network_instances:
            instances = network_instances[contract_type]
            contract_network = resolved_network
            contract_address = ""
            contract_start_block = 0
        else:
            instances = contract_data.get("instances") or [{"label": ""}]
            contract_network = contract_data.get("network", first_network).strip() or first_network
            contract_address = contract_data.get("address", "").strip()
            raw_sb = contract_data.get("startBlock", 0)
            try:
                contract_start_block = int(raw_sb or 0)
            except (ValueError, TypeError):
                contract_start_block = 0

        for inst_idx, inst in enumerate(instances):
            label = inst.get("label", "").strip()
            # The first instance of each contract type must be named exactly
            # `contract_type` (no suffix) so that `graph codegen` generates its
            # output under `generated/{contract_type}/`, which is the directory
            # the mapping file imports from.  Subsequent instances get
            # `contract_type_label` names; their codegen output is identical in
            # content (same ABI) so the mapping doesn't need to import from them.
            if inst_idx == 0:
                ds_name = contract_type
            else:
                ds_name = f"{contract_type}_{label}" if label else f"{contract_type}_{inst_idx}"

            inst_address = inst.get("address", "").strip() or contract_address
            raw_inst_sb = inst.get("startBlock", None)
            if raw_inst_sb is not None:
                try:
                    inst_start_block = int(raw_inst_sb)
                except (ValueError, TypeError):
                    inst_start_block = contract_start_block
            else:
                inst_start_block = contract_start_block

            # Auto-detect deployment block via Etherscan when startBlock is 0
            # and a real address is available.  Requires ETHERSCAN_API_KEY in env.
            _zero = "0x0000000000000000000000000000000000000000"
            if inst_start_block == 0 and inst_address and inst_address != _zero:
                try:
                    from subgraph_wizard.abi.etherscan import get_contract_deployment_block
                    detected = get_contract_deployment_block(contract_network, inst_address)
                    if detected is not None:
                        inst_start_block = detected
                except Exception as exc:
                    logger.warning(
                        "startBlock auto-detection failed for %s on %s: %s",
                        inst_address, contract_network, exc,
                    )

            data_sources.append(
                {
                    "name": ds_name,
                    "contract_type": contract_type,
                    "network": contract_network,
                    "abi_path": abi_path,
                    "address": inst_address or "0x0000000000000000000000000000000000000000",
                    "start_block": inst_start_block,
                    "entities": entity_names or [f"{contract_type}Entity"],
                    "event_handlers": event_handlers,
                }
            )

    context = {
        "subgraph_name": visual_config.get("subgraph_name", "my-subgraph"),
        "data_sources": data_sources,
    }

    logger.info(
        f"Rendering visual subgraph.yaml: {len(data_sources)} data source(s)"
    )
    return render_template("subgraph.yaml.visual.j2", context)
