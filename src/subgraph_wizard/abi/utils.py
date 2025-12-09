"""ABI utility functions.

This module provides functions to parse and extract information from
Ethereum contract ABIs, including event extraction and Solidity-to-GraphQL
type mapping.
"""

import json
import logging
from typing import Any

from subgraph_wizard.errors import ValidationError

logger = logging.getLogger(__name__)


# Mapping from Solidity types to GraphQL/AssemblyScript types
# Reference: https://thegraph.com/docs/en/developing/assemblyscript-api/
SOLIDITY_TO_GRAPH_TYPES: dict[str, str] = {
    # Integer types (signed)
    "int8": "Int",
    "int16": "Int",
    "int24": "Int",
    "int32": "Int",
    "int64": "BigInt",
    "int128": "BigInt",
    "int256": "BigInt",
    "int": "BigInt",  # alias for int256
    # Integer types (unsigned)
    "uint8": "Int",
    "uint16": "Int",
    "uint24": "Int",
    "uint32": "Int",
    "uint64": "BigInt",
    "uint128": "BigInt",
    "uint256": "BigInt",
    "uint": "BigInt",  # alias for uint256
    # Address type
    "address": "Bytes",
    # Boolean type
    "bool": "Boolean",
    # Bytes types
    "bytes": "Bytes",
    "bytes1": "Bytes",
    "bytes2": "Bytes",
    "bytes3": "Bytes",
    "bytes4": "Bytes",
    "bytes8": "Bytes",
    "bytes16": "Bytes",
    "bytes32": "Bytes",
    # String type
    "string": "String",
}


def parse_abi(abi_data: str | list[dict]) -> list[dict[str, Any]]:
    """Parse ABI data from JSON string or list.
    
    Args:
        abi_data: ABI as JSON string or already parsed list of dicts.
    
    Returns:
        List of ABI entries as dictionaries.
    
    Raises:
        ValidationError: If ABI data is invalid.
    """
    if isinstance(abi_data, str):
        try:
            parsed = json.loads(abi_data)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid ABI JSON: {e}")
    else:
        parsed = abi_data
    
    if not isinstance(parsed, list):
        raise ValidationError("ABI must be a JSON array")
    
    return parsed


def validate_abi(abi: list[dict[str, Any]]) -> None:
    """Validate that ABI structure is correct.
    
    Args:
        abi: Parsed ABI list.
    
    Raises:
        ValidationError: If ABI structure is invalid.
    """
    if not isinstance(abi, list):
        raise ValidationError("ABI must be a list")
    
    if len(abi) == 0:
        raise ValidationError("ABI cannot be empty")
    
    for idx, entry in enumerate(abi):
        if not isinstance(entry, dict):
            raise ValidationError(f"ABI entry {idx} must be a dictionary")
        
        if "type" not in entry:
            raise ValidationError(f"ABI entry {idx} missing 'type' field")


def solidity_type_to_graph(solidity_type: str) -> str:
    """Convert a Solidity type to its GraphQL/AssemblyScript equivalent.
    
    Args:
        solidity_type: Solidity type string (e.g., 'uint256', 'address').
    
    Returns:
        GraphQL type string (e.g., 'BigInt', 'Bytes').
    """
    # Handle array types
    if solidity_type.endswith("[]"):
        base_type = solidity_type[:-2]
        graph_type = solidity_type_to_graph(base_type)
        return f"[{graph_type}!]"
    
    # Handle fixed-size array types (e.g., uint256[10])
    if "[" in solidity_type and "]" in solidity_type:
        base_type = solidity_type.split("[")[0]
        graph_type = solidity_type_to_graph(base_type)
        return f"[{graph_type}!]"
    
    # Look up direct mapping
    if solidity_type in SOLIDITY_TO_GRAPH_TYPES:
        return SOLIDITY_TO_GRAPH_TYPES[solidity_type]
    
    # Handle indexed variants of bytesN
    for size in range(1, 33):
        if solidity_type == f"bytes{size}":
            return "Bytes"
    
    # Handle indexed variants of intN/uintN
    for size in [8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 136, 144, 152, 160, 168, 176, 184, 192, 200, 208, 216, 224, 232, 240, 248, 256]:
        if solidity_type == f"int{size}" or solidity_type == f"uint{size}":
            return "BigInt" if size > 32 else "Int"
    
    # Default to Bytes for unknown types
    logger.warning(f"Unknown Solidity type '{solidity_type}', defaulting to Bytes")
    return "Bytes"


def extract_events(abi: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract all events from an ABI.
    
    Args:
        abi: Parsed ABI list.
    
    Returns:
        List of event definitions with name and inputs.
    """
    events = []
    
    for entry in abi:
        if entry.get("type") == "event":
            event_name = entry.get("name", "")
            inputs = entry.get("inputs", [])
            
            if not event_name:
                logger.warning("Found event without name, skipping")
                continue
            
            # Process inputs/parameters
            params = []
            for inp in inputs:
                param_name = inp.get("name", "")
                param_type = inp.get("type", "")
                indexed = inp.get("indexed", False)
                
                if not param_name:
                    # Generate a name for unnamed parameters
                    param_name = f"param{len(params)}"
                
                params.append({
                    "name": param_name,
                    "solidity_type": param_type,
                    "graph_type": solidity_type_to_graph(param_type),
                    "indexed": indexed,
                })
            
            events.append({
                "name": event_name,
                "params": params,
                "signature": build_event_signature(event_name, inputs),
            })
    
    return events


def build_event_signature(event_name: str, inputs: list[dict]) -> str:
    """Build the event signature string for subgraph.yaml.
    
    Args:
        event_name: Name of the event.
        inputs: List of input parameter definitions.
    
    Returns:
        Event signature string (e.g., 'Transfer(address,address,uint256)').
    """
    param_types = []
    for inp in inputs:
        param_type = inp.get("type", "")
        indexed = inp.get("indexed", False)
        
        # Include 'indexed' keyword for indexed parameters
        if indexed:
            param_types.append(f"{param_type} indexed")
        else:
            param_types.append(param_type)
    
    return f"{event_name}({','.join([inp.get('type', '') for inp in inputs])})"


def get_handler_name(event_name: str) -> str:
    """Generate a handler function name for an event.
    
    Args:
        event_name: Name of the event.
    
    Returns:
        Handler function name (e.g., 'handleTransfer').
    """
    return f"handle{event_name}"


def get_entity_name(event_name: str) -> str:
    """Generate an entity name for an event.
    
    For auto mode, we use the event name directly as the entity name.
    
    Args:
        event_name: Name of the event.
    
    Returns:
        Entity name string.
    """
    return event_name


def to_camel_case(name: str) -> str:
    """Convert a name to camelCase for entity field names.
    
    Args:
        name: Original name (may contain underscores).
    
    Returns:
        camelCase version of the name.
    """
    if not name:
        return name
    
    # Split by underscores
    parts = name.split("_")
    
    # First part is lowercase, rest are title case
    result = parts[0].lower()
    for part in parts[1:]:
        result += part.capitalize()
    
    return result
