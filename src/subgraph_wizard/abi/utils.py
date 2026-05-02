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
    # Address type — The Graph codegen generates address params as Address,
    # not raw Bytes, so ports should be typed Address for correct wiring.
    "address": "Address",
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

    Lenient: entries missing a ``"type"`` field are silently skipped rather than
    rejected.  Some ABI generators (whatsabi, older Etherscan exports, bytecode
    decompilers) emit entries without a ``"type"`` key for fallback/receive
    functions or partially-decoded fragments.  Refusing the entire ABI because
    of one such entry is worse than skipping it.

    Args:
        abi: Parsed ABI list.

    Raises:
        ValidationError: If ABI structure is fundamentally invalid (not a list,
            or contains non-dict entries).
    """
    if not isinstance(abi, list):
        raise ValidationError("ABI must be a list")

    if len(abi) == 0:
        raise ValidationError("ABI cannot be empty")

    for idx, entry in enumerate(abi):
        if not isinstance(entry, dict):
            raise ValidationError(f"ABI entry {idx} must be a dictionary")

        if "type" not in entry:
            logger.warning("ABI entry %d missing 'type' field — skipping", idx)


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
    
    # Tuple / struct — components are expanded by callers that have access to
    # the full ABI entry; map the base "tuple" token to Bytes as a safe fallback.
    if solidity_type == "tuple" or solidity_type.startswith("tuple["):
        return "Bytes"

    # Default to Bytes for unknown types
    logger.warning(f"Unknown Solidity type '{solidity_type}', defaulting to Bytes")
    return "Bytes"


def _is_reference_type(solidity_type: str) -> bool:
    """Return True for Solidity types that are reference types when indexed.

    In Ethereum event logs, indexed parameters of reference types (dynamic
    arrays, fixed arrays, bytes, string, and tuples/structs) are ABI-encoded
    and keccak256-hashed before being stored as a log topic.  That means only
    the 32-byte hash is available on-chain; the original value cannot be
    recovered.  graph-cli reflects this by generating ``Bytes`` (not the
    element type) for these parameters.

    Value types — uint*, int*, bool, address, bytesN (fixed-length) — ARE
    stored directly and can be decoded normally.
    """
    # Dynamic arrays (e.g. uint256[], address[], bytes32[][])
    if "[]" in solidity_type:
        return True
    # Fixed-size arrays (e.g. uint256[10])
    if "[" in solidity_type and "]" in solidity_type:
        return True
    # Dynamic bytes and string
    if solidity_type in ("bytes", "string"):
        return True
    # Tuples / structs
    if solidity_type.startswith("tuple"):
        return True
    return False


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
                
                # Indexed reference types (arrays, bytes, string, tuples) are
                # stored as their keccak256 hash in the log topic.  graph-cli
                # therefore generates `Bytes` for them, NOT the expanded element
                # type.  Only value types (uint*, int*, address, bool, bytesN)
                # retain their decoded type when indexed.
                if indexed and _is_reference_type(param_type):
                    graph_type = "Bytes"
                else:
                    graph_type = solidity_type_to_graph(param_type)

                params.append({
                    "name": param_name,
                    "solidity_type": param_type,
                    "graph_type": graph_type,
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
        Event signature string (e.g., 'Transfer(indexed address,indexed address,uint256)').
    """
    param_types = []
    for inp in inputs:
        param_type = inp.get("type", "")
        indexed = inp.get("indexed", False)
        
        # Include 'indexed' keyword for indexed parameters
        # The Graph format is "indexed type", not "type indexed"
        if indexed:
            param_types.append(f"indexed {param_type}")
        else:
            param_types.append(param_type)
    
    return f"{event_name}({','.join(param_types)})"


def extract_read_functions(abi: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract view/pure functions from an ABI.

    These are the contract read functions that can be called inside event
    handlers using The Graph's generated contract bindings.

    Args:
        abi: Parsed ABI list.

    Returns:
        List of read-function definitions, each with name, inputs, outputs,
        and a canonical signature string.
    """
    read_fns = []

    for entry in abi:
        if entry.get("type") != "function":
            continue

        # Accept view/pure state mutability, the legacy constant=True flag, and
        # entries where stateMutability is absent (some ABI generators — whatsabi,
        # bytecode decompilers — omit the field for functions whose mutability
        # they cannot determine).  Explicitly exclude nonpayable/payable write
        # functions so they don't pollute the ContractRead dropdown.
        state_mutability = entry.get("stateMutability", "")
        is_constant = entry.get("constant", False)
        if state_mutability in ("nonpayable", "payable") and not is_constant:
            continue

        fn_name = entry.get("name", "")
        if not fn_name:
            continue

        inputs = entry.get("inputs", [])
        outputs = entry.get("outputs", [])

        def _process_params(params: list[dict]) -> list[dict[str, Any]]:
            result = []
            for i, p in enumerate(params):
                name = p.get("name") or f"param{i}"
                solidity_type = p.get("type", "")
                result.append(
                    {
                        "name": name,
                        "solidity_type": solidity_type,
                        "graph_type": solidity_type_to_graph(solidity_type),
                    }
                )
            return result

        def _process_outputs(params: list[dict]) -> list[dict[str, Any]]:
            """Like _process_params but expands tuple outputs into their components.

            When a function returns a struct (tuple), viem's readContract returns
            a plain object whose keys are the component names.  Expanding the
            components into individual output entries lets the canvas expose one
            port per field and lets the compiler generate ``result.fieldName``
            accessors instead of an opaque Bytes value.
            """
            result = []
            for i, p in enumerate(params):
                name = p.get("name") or f"param{i}"
                solidity_type = p.get("type", "")
                components = p.get("components", [])
                if solidity_type == "tuple" and components:
                    for comp in components:
                        comp_name = comp.get("name") or f"field{len(result)}"
                        comp_type = comp.get("type", "")
                        result.append(
                            {
                                "name": comp_name,
                                "solidity_type": comp_type,
                                "graph_type": solidity_type_to_graph(comp_type),
                                "is_tuple_component": True,
                            }
                        )
                else:
                    result.append(
                        {
                            "name": name,
                            "solidity_type": solidity_type,
                            "graph_type": solidity_type_to_graph(solidity_type),
                        }
                    )
            return result

        processed_inputs = _process_params(inputs)
        processed_outputs = _process_outputs(outputs)

        # Canonical signature uses raw Solidity types, no 'indexed' keyword
        input_types = ",".join(p.get("type", "") for p in inputs)
        signature = f"{fn_name}({input_types})"

        read_fns.append(
            {
                "name": fn_name,
                "inputs": processed_inputs,
                "outputs": processed_outputs,
                "signature": signature,
            }
        )

    return read_fns


def get_handler_name(event_name: str) -> str:
    """Generate a handler function name for an event.

    The result always capitalises the first character of ``event_name`` so that
    ``transfer`` and ``Transfer`` both produce ``handleTransfer``.  This matches
    the behaviour of ``_handler_name()`` in graph_compiler.py, which is the
    function that actually emits the ``export function handle…`` declaration in
    the AssemblyScript mapping file.  The two must stay in sync so that the
    ``handler:`` field in subgraph.yaml always matches the exported name.

    Args:
        event_name: Name of the event.

    Returns:
        Handler function name (e.g., 'handleTransfer').
    """
    if not event_name:
        return "handleUnknownEvent"
    return f"handle{event_name[0].upper()}{event_name[1:]}"


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
