"""Visual graph validator.

Validates a visual-config.json graph and returns a list of structured
error/warning objects. These are returned by POST /api/validate and also
consumed by the frontend to highlight problem nodes and edges.

Error structure:
  {
    "level":   "error" | "warning",
    "code":    str,          # machine-readable code e.g. "MISSING_ID"
    "message": str,          # human-readable description
    "node_id": str | None,   # canvas node that caused the issue
    "edge_id": str | None,   # canvas edge that caused the issue
  }

Validation rules
────────────────
Errors (block generation):
  CONTRACT_NO_NAME          — Contract node has no type name
  CONTRACT_NO_ABI           — Contract node has no ABI loaded
  ENTITY_NO_NAME            — Entity node has no entity name
  ENTITY_NO_ID_WIRED        — Entity node has no value wired to its id field
  TYPE_MISMATCH             — Edge connects ports with incompatible Graph types
  CONTRACTREAD_NO_CONTRACT  — ContractRead node has no contract selected
  CONTRACTREAD_BAD_FN_INDEX — ContractRead node function index out of range
  AGGREGATE_NO_NAME         — Aggregate entity node has no name
  AGGREGATE_NO_ID_WIRED     — Aggregate entity node has no value wired to its id field

Warnings (generation continues but output may be incomplete):
  CONTRACT_EMPTY_INSTANCE         — A contract instance row has no address
  ENTITY_NO_FIELDS                — Entity has only the id field (and it's not wired)
  ENTITY_REQUIRED_FIELD_UNWIRED   — A required entity field has no wire and may not auto-fill
  ENTITY_NO_EVENT_TRIGGER         — Entity has only per-param wires; no event trigger wire found
  DISCONNECTED_CONTRACT           — Contract node has no events wired to any entity
  DISCONNECTED_ENTITY             — Entity node has no incoming wired fields at all
  MATH_DISCONNECTED_INPUT         — Math/concat node has an unwired input
  STRCONCAT_DISCONNECTED          — String Concat node has an unwired input
  CONDITIONAL_NO_CONDITION        — Conditional node has no condition wired (guard never fires)
  TYPECAST_BAD_INDEX              — TypeCast castIndex out of valid range (0–6)
  AGGREGATE_NO_FIELDS             — Aggregate entity has no field-in-* wires (only id)
  AGGREGATE_REQUIRED_FIELD_UNWIRED     — A required aggregate field has no field-in-* wire
  DISCONNECTED_AGGREGATE               — Aggregate entity node has no incoming connections
  CONTRACTREAD_NO_BIND_ADDRESS         — ContractRead contract has no address; will silently call event.address
  ENTITY_CONDITIONAL_SAVE_RISK         — All required fields are conditional; a null-field .save() may be rejected
  CONTRACT_START_BLOCK_ZERO            — A contract instance has startBlock=0; subgraph will index from genesis
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Graph type compatibility table ────────────────────────────────────────────
# Maps source Graph type → set of compatible target Graph types.
# "any" is a wildcard that accepts everything.

# Primitive types known to the type system (everything else is an entity reference)
_GQL_PRIMITIVES: frozenset[str] = frozenset({
    "ID", "String", "Bytes", "Boolean", "Int", "BigInt", "BigDecimal", "Address",
})

_COMPATIBLE: dict[str, set[str]] = {
    "BigInt":     {"BigInt", "any"},
    "Int":        {"Int", "BigInt", "any"},
    "BigDecimal": {"BigDecimal", "any"},
    "Bytes":      {"Bytes", "Address", "String", "ID", "any"},
    "Address":    {"Address", "Bytes", "String", "ID", "any"},
    "String":     {"String", "ID", "any"},
    "Boolean":    {"Boolean", "any"},
    "ID":         {"ID", "String", "any"},
    "any":        {"BigInt", "Int", "BigDecimal", "Bytes", "Address", "String", "Boolean", "ID", "any"},
}


def _types_compatible(from_type: str, to_type: str) -> bool:
    """Return True if a value of from_type can be wired to a port expecting to_type."""
    if from_type == to_type:
        return True
    return to_type in _COMPATIBLE.get(from_type, set())


# ── Port type resolvers ───────────────────────────────────────────────────────

def _source_port_type(
    node: dict[str, Any],
    handle: str,
    nodes_by_id: dict[str, dict[str, Any]],
) -> str:
    """Infer the Graph type produced by a source (output) port."""
    node_type = node.get("type", "")
    data = node.get("data", {})

    if node_type == "contract":
        # event-{EventName}-{paramName} → look up in events list
        if handle.startswith("event-") and handle.count("-") >= 2:
            parts = handle.split("-", 2)
            event_name, param_name = parts[1], parts[2]
            for ev in data.get("events", []):
                if ev.get("name") == event_name:
                    for p in ev.get("params", []):
                        if p.get("name") == param_name:
                            return p.get("graph_type", "any")
        # implicit-address, implicit-block-number, etc.
        if handle in ("implicit-address", "implicit-instance-address"):
            return "Address"
        if handle in ("implicit-block-number", "implicit-block-timestamp"):
            return "BigInt"
        if handle == "implicit-tx-hash":
            return "Bytes"
        return "any"

    if node_type == "math":
        return "BigInt"

    if node_type == "typecast":
        cast_index = data.get("castIndex", 0)
        _CAST_TO = ["Int", "String", "String", "Address", "Bytes", "String", "Bytes"]
        return _CAST_TO[cast_index] if cast_index < len(_CAST_TO) else "any"

    if node_type == "strconcat":
        return "String"

    if node_type == "conditional":
        return "any"

    if node_type == "aggregateentity":
        # field-out-id — exposes the aggregate's stable ID as an output
        if handle == "field-out-id":
            return "ID"
        # field-prev-{name} — return the declared type of that field
        if handle.startswith("field-prev-"):
            field_name = handle[len("field-prev-"):]
            for f in data.get("fields", []):
                if f.get("name") == field_name:
                    return f.get("type", "any")
        return "any"

    if node_type == "contractread":
        fn_index = data.get("fnIndex", 0)
        ref_id = data.get("contractNodeId", "")
        ref_node = nodes_by_id.get(ref_id)
        if ref_node:
            read_fns = ref_node["data"].get("readFunctions", [])
            if fn_index < len(read_fns):
                outputs = read_fns[fn_index].get("outputs", [])
                if handle.startswith("out-"):
                    out_name = handle[4:]
                    for o in outputs:
                        if o.get("name") == out_name:
                            return o.get("graph_type", "any")
        return "any"

    return "any"


def _target_port_type(
    node: dict[str, Any],
    handle: str,
    nodes_by_id: dict[str, dict[str, Any]],
) -> str:
    """Infer the Graph type expected by a target (input) port."""
    node_type = node.get("type", "")
    data = node.get("data", {})

    if node_type == "entity":
        # field-{name} → look up in fields list
        if handle.startswith("field-"):
            field_name = handle[6:]
            for f in data.get("fields", []):
                if f.get("name") == field_name:
                    ftype = f.get("type", "any")
                    # Entity-ref types (e.g. AlchemistTVL) accept any ID-like value
                    if ftype not in _GQL_PRIMITIVES:
                        return "any"
                    return ftype
        return "any"

    if node_type == "math":
        return "BigInt"  # both inputs expect BigInt

    if node_type == "typecast":
        cast_index = data.get("castIndex", 0)
        _CAST_FROM = ["BigInt", "BigInt", "Bytes", "Bytes", "String", "Address", "Address"]
        return _CAST_FROM[cast_index] if cast_index < len(_CAST_FROM) else "any"

    if node_type == "strconcat":
        return "String"

    if node_type == "conditional":
        if handle == "condition":
            return "Boolean"
        return "any"

    if node_type == "contractread":
        if handle == "bind-address":
            return "Address"
        fn_index = data.get("fnIndex", 0)
        ref_id = data.get("contractNodeId", "")
        ref_node = nodes_by_id.get(ref_id)
        if ref_node:
            read_fns = ref_node["data"].get("readFunctions", [])
            if fn_index < len(read_fns):
                inputs = read_fns[fn_index].get("inputs", [])
                if handle.startswith("in-"):
                    arg_name = handle[3:]
                    for inp in inputs:
                        if inp.get("name") == arg_name:
                            return inp.get("graph_type", "any")
        return "any"

    return "any"


# ── Event handle classifiers ──────────────────────────────────────────────────


def _is_event_trigger_handle(handle: str) -> bool:
    """Return True for 2-part event handles like ``event-Transfer`` (trigger ports).

    These are the handles that the compiler's BFS uses to discover which entities
    belong to a handler.  The format is exactly ``event-{EventName}`` with no
    further dashes (other than the one separator).
    """
    parts = handle.split("-")
    return len(parts) == 2 and parts[0] == "event"


def _is_event_param_handle(handle: str) -> bool:
    """Return True for 3+-part event handles like ``event-Transfer-amount`` (param ports).

    These carry individual event parameter values.  Unlike trigger handles they
    do NOT cause the compiler to include the target entity in the handler's BFS
    traversal.
    """
    parts = handle.split("-")
    return len(parts) >= 3 and parts[0] == "event"


# ── Main validator ────────────────────────────────────────────────────────────


def validate_graph(visual_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a visual graph config and return a list of issues.

    Args:
        visual_config: Parsed visual-config.json dict.

    Returns:
        List of issue dicts with keys: level, code, message, node_id, edge_id.
    """
    issues: list[dict[str, Any]] = []

    nodes: list[dict[str, Any]] = visual_config.get("nodes", [])
    edges: list[dict[str, Any]] = visual_config.get("edges", [])
    nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in nodes}

    # Build a set of contract type names that have at least one instance with
    # a non-zero startBlock in the Networks panel config.  These contracts are
    # exempt from the CONTRACT_START_BLOCK_ZERO warning because the user has
    # set the start block in the Networks panel rather than the inline field.
    _networks_have_start_block: set[str] = set()
    for _net_entry in visual_config.get("networks", []):
        for _ct_name, _ct_data in _net_entry.get("contracts", {}).items():
            for _inst in _ct_data.get("instances", []):
                try:
                    if int(_inst.get("startBlock") or 0) > 0:
                        _networks_have_start_block.add(_ct_name)
                        break
                except (ValueError, TypeError):
                    pass

    # Build quick lookup: which target handles have incoming edges
    wired_targets: set[tuple[str, str]] = {
        (e["target"], e.get("targetHandle", "")) for e in edges
    }
    # Source nodes that have at least one outgoing edge
    wired_sources: set[str] = {e["source"] for e in edges}

    def _err(code, message, node_id=None, edge_id=None):
        issues.append({
            "level": "error",
            "code": code,
            "message": message,
            "node_id": node_id,
            "edge_id": edge_id,
        })

    def _warn(code, message, node_id=None, edge_id=None):
        issues.append({
            "level": "warning",
            "code": code,
            "message": message,
            "node_id": node_id,
            "edge_id": edge_id,
        })

    # ── Per-node checks ────────────────────────────────────────────────────────
    for node in nodes:
        nid = node["id"]
        ntype = node.get("type", "")
        data = node.get("data", {})

        if ntype == "contract":
            if not data.get("name", "").strip():
                _err("CONTRACT_NO_NAME", "Contract node has no type name.", node_id=nid)

            if not data.get("abi"):
                _err("CONTRACT_NO_ABI", f"Contract node '{data.get('name', nid)}' has no ABI loaded.", node_id=nid)

            # Check that at least one event port has an outgoing edge
            events = data.get("events", [])
            if events:
                event_port_ids = {f"event-{ev['name']}" for ev in events}
                has_wired_event = any(
                    e["source"] == nid and e.get("sourceHandle", "") in event_port_ids
                    for e in edges
                )
                if not has_wired_event:
                    _warn(
                        "DISCONNECTED_CONTRACT",
                        f"Contract '{data.get('name', nid)}' has no events wired to any entity or aggregate.",
                        node_id=nid,
                    )

            # Warn when any instance has startBlock=0 (or unset).
            # The generator tries Etherscan auto-detection, but it silently falls
            # back to 0 if the API key is missing or the request fails.  Indexing
            # from block 0 is extremely slow and may timeout on hosted services.
            #
            # Skip the warning when the Networks panel already has a non-zero
            # startBlock for this contract — the user has configured it there
            # instead of in the node's inline field.
            contract_name = data.get("name", nid)
            if contract_name not in _networks_have_start_block:
                instances = data.get("instances") or [{"label": "", "startBlock": data.get("startBlock", 0)}]
                for inst in instances:
                    raw_sb = inst.get("startBlock", 0)
                    try:
                        sb = int(raw_sb or 0)
                    except (ValueError, TypeError):
                        sb = 0
                    if sb == 0:
                        label = inst.get("label", "").strip()
                        inst_desc = f" (instance '{label}')" if label else ""
                        _warn(
                            "CONTRACT_START_BLOCK_ZERO",
                            f"Contract '{contract_name}'{inst_desc} has startBlock=0. "
                            f"If Etherscan auto-detection is unavailable, the subgraph will "
                            f"index from genesis, which is extremely slow. Set an explicit "
                            f"startBlock to the block where the contract was deployed.",
                            node_id=nid,
                        )
                        break  # one warning per contract node is enough

        elif ntype == "entity":
            if not data.get("name", "").strip():
                _err("ENTITY_NO_NAME", "Entity node has no name.", node_id=nid)

            fields = data.get("fields", [])
            non_id_fields = [f for f in fields if f.get("name") != "id"]

            # Check id field is wired — only required when ID strategy is 'custom'
            # (tx_hash / tx_hash_log / event_address auto-generate the id in code)
            id_strategy = data.get("idStrategy", "custom")
            if id_strategy == "custom":
                if ("field-id" not in {h for (tid, h) in wired_targets if tid == nid}):
                    _err(
                        "ENTITY_NO_ID_WIRED",
                        f"Entity '{data.get('name', nid)}' has no value wired to its 'id' field.",
                        node_id=nid,
                    )

            # Warn if no non-id fields wired
            wired_field_handles = {h for (tid, h) in wired_targets if tid == nid and h != "field-id"}
            if not wired_field_handles and non_id_fields:
                _warn(
                    "ENTITY_NO_FIELDS",
                    f"Entity '{data.get('name', nid)}' has no fields wired (other than id).",
                    node_id=nid,
                )

            # Warn for required fields that have no wire.
            # Required fields with no incoming wire and no name-match auto-fill will
            # produce a null value at runtime, which graph-node rejects with a
            # null-constraint error and marks the event as failed.
            for fld in non_id_fields:
                fname = fld.get("name", "")
                if not fname:
                    continue
                if not fld.get("required", False):
                    continue
                fhandle = f"field-{fname}"
                if (nid, fhandle) not in wired_targets:
                    _warn(
                        "ENTITY_REQUIRED_FIELD_UNWIRED",
                        f"Entity '{data.get('name', nid)}': required field '{fname}' has no wire. "
                        f"If no event param named '{fname}' exists, this field will be null at "
                        f"runtime and graph-node will reject the save.",
                        node_id=nid,
                    )

            # Warn when ALL required non-id fields are wired exclusively from
            # conditional nodes.  The compiler guards each field assignment with
            # "if (cond) { ... }" but always emits entity.save().  If all
            # conditions evaluate to false at runtime, the entity is saved with
            # null required fields and graph-node rejects the save.
            required_field_names = {
                fld.get("name", "")
                for fld in non_id_fields
                if fld.get("required", False) and fld.get("name", "")
            }
            if required_field_names:
                # For each required field, check whether every incoming wire for
                # that field comes from a conditional node source.
                def _all_wires_conditional(field_handle: str) -> bool:
                    wires = [
                        e for e in edges
                        if e.get("target") == nid and e.get("targetHandle") == field_handle
                    ]
                    if not wires:
                        return False  # no wire → separate REQUIRED_FIELD_UNWIRED handles this
                    return all(
                        (nodes_by_id.get(e["source"]) or {}).get("type") == "conditional"
                        for e in wires
                    )

                all_required_conditional = all(
                    _all_wires_conditional(f"field-{fn}")
                    for fn in required_field_names
                )
                if all_required_conditional:
                    _warn(
                        "ENTITY_CONDITIONAL_SAVE_RISK",
                        f"Entity '{data.get('name', nid)}': every required field is wired "
                        f"through a conditional node. If all conditions evaluate to false at "
                        f"runtime, the entity will be saved with null required fields and "
                        f"graph-node will reject the save. Consider wiring the entity's 'evt' "
                        f"handle directly from the same conditional output to gate the entire "
                        f"block, or ensure at least one required field has an unconditional wire.",
                        node_id=nid,
                    )

            # Warn when ALL incoming edges to this entity come from per-param
            # contract ports (event-{Name}-{param}) rather than from event trigger
            # ports (event-{Name}).  The compiler discovers entities via the trigger
            # port BFS; per-param-only wires are silently ignored and the entity
            # will not be included in any handler.
            # Entities connected through transform nodes (math, typecast, etc.) or
            # with triggerEvents selections are exempt from this check.
            entity_incoming = [e for e in edges if e.get("target") == nid]
            has_trigger_wire = any(
                _is_event_trigger_handle(e.get("sourceHandle", ""))
                for e in entity_incoming
            )
            has_param_only_wire = any(
                _is_event_param_handle(e.get("sourceHandle", ""))
                for e in entity_incoming
            )
            has_trigger_events = bool(data.get("triggerEvents"))
            if (
                entity_incoming
                and not has_trigger_wire
                and has_param_only_wire
                and not has_trigger_events
            ):
                _warn(
                    "ENTITY_NO_EVENT_TRIGGER",
                    f"Entity '{data.get('name', nid)}' has wires from per-parameter ports "
                    f"(e.g. event-Transfer-amount) but no trigger wire from an event port "
                    f"(e.g. event-Transfer → evt). The entity will not be included in any handler. "
                    f"Add a wire from the event's trigger port to this entity's 'evt' handle.",
                    node_id=nid,
                )

            # Disconnected entirely
            if nid not in {e["target"] for e in edges}:
                _warn(
                    "DISCONNECTED_ENTITY",
                    f"Entity '{data.get('name', nid)}' has no incoming connections.",
                    node_id=nid,
                )

        elif ntype == "math":
            for port in ("left", "right"):
                if (nid, port) not in wired_targets:
                    _warn(
                        "MATH_DISCONNECTED_INPUT",
                        f"Math node '{nid}' has no value wired to '{port}' — will use BigInt.zero().",
                        node_id=nid,
                    )

        elif ntype == "strconcat":
            for port in ("left", "right"):
                if (nid, port) not in wired_targets:
                    _warn(
                        "STRCONCAT_DISCONNECTED",
                        f"String Concat node '{nid}' has no value wired to '{port}' — will use empty string.",
                        node_id=nid,
                    )

        elif ntype == "typecast":
            _CAST_MAX_INDEX = 6
            cast_index = data.get("castIndex", 0)
            if not isinstance(cast_index, int) or cast_index < 0 or cast_index > _CAST_MAX_INDEX:
                _warn(
                    "TYPECAST_BAD_INDEX",
                    f"TypeCast node '{nid}' has an invalid castIndex ({cast_index!r}); "
                    f"must be 0–{_CAST_MAX_INDEX}.",
                    node_id=nid,
                )

        elif ntype == "conditional":
            if (nid, "condition") not in wired_targets:
                _warn(
                    "CONDITIONAL_NO_CONDITION",
                    f"Conditional node '{nid}' has no condition wired — the guard will never fire.",
                    node_id=nid,
                )

        elif ntype == "aggregateentity":
            if not data.get("name", "").strip():
                _err("AGGREGATE_NO_NAME", "Aggregate entity node has no name.", node_id=nid)

            # id must always be wired for aggregates
            if ("field-id" not in {h for (tid, h) in wired_targets if tid == nid}):
                _err(
                    "AGGREGATE_NO_ID_WIRED",
                    f"Aggregate entity '{data.get('name', nid)}' has no value wired to its 'id' field.",
                    node_id=nid,
                )

            # Warn if no field-in-* ports are wired (only id)
            wired_in_handles = {h for (tid, h) in wired_targets if tid == nid and h.startswith("field-in-")}
            if not wired_in_handles:
                _warn(
                    "AGGREGATE_NO_FIELDS",
                    f"Aggregate entity '{data.get('name', nid)}' has no field inputs wired (field-in-*).",
                    node_id=nid,
                )

            # Warn for required fields with no field-in-* wire.
            # graph-node will reject .save() at runtime if a required field is null.
            agg_non_id = [f for f in data.get("fields", []) if f.get("name") not in ("id", "")]
            for fld in agg_non_id:
                fname = fld.get("name", "")
                if not fname:
                    continue
                if not fld.get("required", False):
                    continue
                fhandle = f"field-in-{fname}"
                if (nid, fhandle) not in wired_targets:
                    _warn(
                        "AGGREGATE_REQUIRED_FIELD_UNWIRED",
                        f"Aggregate entity '{data.get('name', nid)}': required field '{fname}' "
                        f"has no field-in-{fname} wire. It will be null at runtime and "
                        f"graph-node will reject the save.",
                        node_id=nid,
                    )

            # Disconnected entirely — OK if triggerEvents checklist has selections
            has_trigger_events = bool(data.get("triggerEvents"))
            if nid not in {e["target"] for e in edges} and not has_trigger_events:
                _warn(
                    "DISCONNECTED_AGGREGATE",
                    f"Aggregate entity '{data.get('name', nid)}' has no incoming connections "
                    f"and no trigger events selected.",
                    node_id=nid,
                )

        elif ntype == "contractread":
            ref_contract_id = data.get("contractNodeId", "")
            # If contractNodeId is empty, apply the same fallback the UI uses:
            # resolve to the first contract node on the canvas. This avoids false-
            # positive errors when a node was saved before its contract was persisted
            # (e.g. when all contracts are collapsed and the component never mounted).
            if not ref_contract_id:
                first_contract = next(
                    (n for n in nodes if n.get("type") == "contract" and n.get("data", {}).get("name")),
                    None,
                )
                ref_contract_id = first_contract["id"] if first_contract else ""
            if not ref_contract_id or ref_contract_id not in nodes_by_id:
                _err(
                    "CONTRACTREAD_NO_CONTRACT",
                    f"Contract Read node '{nid}' has no contract selected.",
                    node_id=nid,
                )
            else:
                ref_node = nodes_by_id[ref_contract_id]
                read_fns = ref_node["data"].get("readFunctions", [])
                fn_index = data.get("fnIndex", 0)
                if not isinstance(fn_index, int) or fn_index < 0 or fn_index >= max(len(read_fns), 1):
                    _err(
                        "CONTRACTREAD_BAD_FN_INDEX",
                        f"Contract Read node '{nid}' function index ({fn_index}) is out of range "
                        f"(contract has {len(read_fns)} read function(s)).",
                        node_id=nid,
                    )

                # Warn when neither a bind-address wire nor a configured contract
                # address exists.  The compiler falls back to event.address in this
                # case, which calls the read function on the event-emitting contract
                # rather than the intended contract — almost certainly wrong.
                has_bind_wire = (nid, "bind-address") in wired_targets
                if not has_bind_wire:
                    ref_data = ref_node.get("data", {})
                    # Check new-style per-row addresses
                    instances = ref_data.get("instances", [])
                    has_address = any(
                        inst.get("address", "").strip()
                        for inst in instances
                    )
                    # Also check legacy flat address field
                    if not has_address:
                        has_address = bool(ref_data.get("address", "").strip())
                    if not has_address:
                        _warn(
                            "CONTRACTREAD_NO_BIND_ADDRESS",
                            f"Contract Read node '{nid}' references contract "
                            f"'{ref_data.get('name', ref_contract_id)}' which has no "
                            f"configured address and no bind-address wire. The compiler "
                            f"will fall back to event.address, which may call the wrong "
                            f"contract. Wire a bind-address or add an address to the contract.",
                            node_id=nid,
                        )

    # ── Ponder-mode-specific checks ───────────────────────────────────────────
    output_mode = visual_config.get("output_mode", "graph")
    if output_mode == "ponder":
        # Warn for BigDecimal fields — Ponder has no native decimal type
        for node in nodes:
            ntype = node.get("type", "")
            if ntype not in ("entity", "aggregateentity"):
                continue
            nid = node["id"]
            data = node.get("data", {})
            for fld in data.get("fields", []):
                if fld.get("type") == "BigDecimal":
                    fname = fld.get("name", "?")
                    _warn(
                        "PONDER_BIGDECIMAL_UNSUPPORTED",
                        f"Entity '{data.get('name', nid)}' field '{fname}' is BigDecimal. "
                        f"Ponder has no native decimal type — it will be stored as text. "
                        f"Consider changing the field type to BigInt (store values in base units "
                        f"like wei) or String.",
                        node_id=nid,
                    )

        # Warn for unknown chain IDs
        try:
            from subgraph_wizard.generate.ponder_config import CHAIN_IDS
        except ImportError:
            CHAIN_IDS = {}
        networks_cfg: list[dict[str, Any]] = visual_config.get("networks", [])
        for net_entry in networks_cfg:
            slug = net_entry.get("network", "").strip()
            if slug and slug not in CHAIN_IDS:
                _warn(
                    "PONDER_UNKNOWN_CHAIN_ID",
                    f"Network '{slug}' is not in the known chain ID table. "
                    f"Ponder requires a numeric chain ID — the generated ponder.config.ts "
                    f"will use id: 0 as a placeholder. Update it manually before deploying.",
                )

    # ── Per-edge type checks ───────────────────────────────────────────────────
    for edge in edges:
        eid = edge.get("id", "")
        src_id = edge.get("source", "")
        src_handle = edge.get("sourceHandle", "")
        tgt_id = edge.get("target", "")
        tgt_handle = edge.get("targetHandle", "")

        src_node = nodes_by_id.get(src_id)
        tgt_node = nodes_by_id.get(tgt_id)

        if not src_node or not tgt_node:
            continue

        src_type = _source_port_type(src_node, src_handle, nodes_by_id)
        tgt_type = _target_port_type(tgt_node, tgt_handle, nodes_by_id)

        # Skip checks when either side is "any" (wildcard)
        if src_type == "any" or tgt_type == "any":
            continue

        if not _types_compatible(src_type, tgt_type):
            _err(
                "TYPE_MISMATCH",
                (
                    f"Type mismatch: '{src_type}' (from {src_node['data'].get('name', src_id)}.{src_handle}) "
                    f"cannot be assigned to '{tgt_type}' "
                    f"(field {tgt_node['data'].get('name', tgt_id)}.{tgt_handle})."
                ),
                edge_id=eid,
            )

    return issues


def has_errors(issues: list[dict[str, Any]]) -> bool:
    """Return True if any issue has level='error'."""
    return any(i["level"] == "error" for i in issues)
