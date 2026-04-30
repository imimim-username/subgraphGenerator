"""Graph simulator: visual graph → human-readable subgraph description.

Produces structured JSON describing what the subgraph will do, without
emitting AssemblyScript.  Used by the /api/simulate endpoint to power the
canvas Simulate panel.

Output shape:
  {
    "handlers": [
      {
        "contract": "alchemistV3",
        "event": "Deposit",
        "steps": [
          {"type": "contract_read", "label": "...", "result": "..."},
          {"type": "entity_load",   "entity": "MYTtvl", "id_source": "..."},
          {"type": "field_write",   "entity": "MYTtvl", "field": "tvl", "source": "..."},
          {"type": "entity_save",   "entity": "MYTtvl"},
        ]
      },
      ...
    ],
    "schema": [
      {
        "name": "MYTtvl",
        "is_aggregate": true,
        "fields": [{"name": "id", "type": "ID", "required": true}, ...]
      },
      ...
    ],
    "queries": [
      {
        "entity": "MYTtvl",
        "singular": "mYTtvl",
        "plural": "mYTtvls",
        "fields": ["id", "tvl", "blockNumber", "timestamp"]
      },
      ...
    ]
  }
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ── Shared edge dataclass (mirrors graph_compiler.Edge) ───────────────────────

@dataclass
class _Edge:
    id: str
    source: str
    source_handle: str
    target: str
    target_handle: str


# ── Human-readable implicit port labels ───────────────────────────────────────

_IMPLICIT_LABELS: dict[str, str] = {
    "implicit-address":          "contract address (event emitter)",
    "implicit-instance-address": "deployed address",
    "implicit-tx-hash":          "transaction hash",
    "implicit-block-number":     "block number",
    "implicit-block-timestamp":  "block timestamp",
}

_CAST_LABELS = [
    "→ Int (toI32)",
    "→ String (toString)",
    "→ String (toHexString)",
    "→ Address (fromBytes)",
    "→ Bytes (fromHexString)",
    "→ String (toHexString)",
    "→ Bytes (as Bytes)",
]

_MATH_OP_LABELS = {
    "add":      "+",
    "subtract": "−",
    "multiply": "×",
    "divide":   "÷",
    "mod":      "mod",
    "pow":      "^",
}


# ── Simulator ─────────────────────────────────────────────────────────────────

class GraphSimulator:
    """Describe a visual graph config in human-readable structured JSON."""

    def __init__(self, visual_config: dict[str, Any]) -> None:
        self._config = visual_config
        self._nodes: dict[str, dict[str, Any]] = {
            n["id"]: n for n in visual_config.get("nodes", [])
        }
        raw_edges = visual_config.get("edges", [])
        self._edges: list[_Edge] = [
            _Edge(
                id=e["id"],
                source=e["source"],
                source_handle=e.get("sourceHandle", ""),
                target=e["target"],
                target_handle=e.get("targetHandle", ""),
            )
            for e in raw_edges
        ]
        self._edge_by_target: dict[tuple[str, str], _Edge] = {
            (e.target, e.target_handle): e for e in self._edges
        }
        self._edges_from: dict[str, list[_Edge]] = defaultdict(list)
        for e in self._edges:
            self._edges_from[e.source].append(e)

    # ── Public API ─────────────────────────────────────────────────────────────

    def simulate(self) -> dict[str, Any]:
        """Return the full simulation description."""
        schema = self._build_schema()
        queries = [self._build_query(s) for s in schema]
        handlers = self._build_handlers()
        return {
            "handlers": handlers,
            "schema": schema,
            "queries": queries,
        }

    # ── Schema ─────────────────────────────────────────────────────────────────

    def _build_schema(self) -> list[dict[str, Any]]:
        result = []
        for node in self._nodes.values():
            if node.get("type") not in ("entity", "aggregateentity"):
                continue
            data = node["data"]
            name = data.get("name", "").strip()
            if not name:
                continue
            fields_out = []
            for f in data.get("fields", []):
                fname = f.get("name", "").strip()
                if not fname:
                    continue
                fields_out.append({
                    "name":       fname,
                    "type":       f.get("type", "String"),
                    "required":   bool(f.get("required") or fname == "id"),
                    "derivedFrom": f.get("derivedFrom") or None,
                })
            result.append({
                "name":         name,
                "is_aggregate": node.get("type") == "aggregateentity",
                "fields":       fields_out,
            })
        return result

    def _build_query(self, schema_entry: dict[str, Any]) -> dict[str, Any]:
        name = schema_entry["name"]
        # GraphQL convention: singular = lowerCamelCase, plural = + 's'
        singular = name[0].lower() + name[1:]
        plural   = singular + "s"
        return {
            "entity":   name,
            "singular": singular,
            "plural":   plural,
            "fields":   [f["name"] for f in schema_entry["fields"] if not f.get("derivedFrom")],
        }

    # ── Handlers ───────────────────────────────────────────────────────────────

    def _build_handlers(self) -> list[dict[str, Any]]:
        handlers = []
        contract_nodes = [
            n for n in self._nodes.values() if n.get("type") == "contract"
        ]
        for contract_node in contract_nodes:
            data = contract_node["data"]
            contract_name = data.get("name", "")
            if not contract_name:
                continue
            contract_id = contract_node["id"]
            for event in data.get("events", []):
                h = self._describe_handler(contract_node, contract_id, contract_name, event)
                if h:
                    handlers.append(h)
        return handlers

    def _describe_handler(
        self,
        contract_node: dict[str, Any],
        contract_id: str,
        contract_name: str,
        event: dict[str, Any],
    ) -> dict[str, Any] | None:
        event_name = event.get("name", "")
        if not event_name:
            return None
        event_port_id = f"event-{event_name}"

        # Collect entity nodes triggered by this event
        all_entities: dict[str, dict[str, Any]] = {}

        # Direct wires from the event output port
        for edge in self._edges_from.get(contract_id, []):
            if edge.source_handle == event_port_id:
                target = self._nodes.get(edge.target)
                if target and target.get("type") in ("entity", "aggregateentity"):
                    all_entities[edge.target] = target

        # Transitively reachable entities (through transform nodes)
        all_entities.update(self._find_reachable_entities(contract_id, event_port_id))

        # triggerEvents checklist — both aggregateentity and regular entity nodes
        for node in self._nodes.values():
            if node.get("type") not in ("aggregateentity", "entity"):
                continue
            for trigger in node["data"].get("triggerEvents", []):
                if (
                    trigger.get("contractId") == contract_id
                    and trigger.get("eventName") == event_name
                ):
                    all_entities[node["id"]] = node

        if not all_entities:
            return None

        steps: list[dict[str, Any]] = []

        # Sort: aggregates first, then regular entities
        sorted_entities = sorted(
            all_entities.values(),
            key=lambda n: (0 if n.get("type") == "aggregateentity" else 1),
        )

        for entity_node in sorted_entities:
            entity_steps = self._describe_entity_steps(
                entity_node, event_name, contract_name, contract_id
            )
            steps.extend(entity_steps)

        return {
            "contract": contract_name,
            "event":    event_name,
            "steps":    steps,
        }

    def _find_reachable_entities(
        self, start_node_id: str, start_port_id: str
    ) -> dict[str, dict[str, Any]]:
        """BFS from a contract event port through transform nodes to entity nodes."""
        found: dict[str, dict[str, Any]] = {}
        queue: list[tuple[str, str]] = [(start_node_id, start_port_id)]
        visited: set[tuple[str, str]] = set()

        while queue:
            node_id, port_id = queue.pop(0)
            if (node_id, port_id) in visited:
                continue
            visited.add((node_id, port_id))

            for edge in self._edges_from.get(node_id, []):
                if edge.source_handle != port_id:
                    continue
                target = self._nodes.get(edge.target)
                if not target:
                    continue
                t = target.get("type", "")
                if t in ("entity", "aggregateentity"):
                    found[target["id"]] = target
                elif t in ("math", "typecast", "strconcat", "conditional", "contractread"):
                    for out_port in self._output_ports_of(target):
                        queue.append((target["id"], out_port))

        return found

    def _output_ports_of(self, node: dict[str, Any]) -> list[str]:
        t = node.get("type", "")
        if t in ("math", "typecast", "strconcat"):
            return ["result"]
        if t == "conditional":
            return ["value-out"]
        if t == "contractread":
            fn_index = node["data"].get("fnIndex", 0)
            cr_contract = self._nodes.get(node["data"].get("contractNodeId", ""))
            if cr_contract:
                read_fns = cr_contract["data"].get("readFunctions", [])
                if fn_index < len(read_fns):
                    return [f"out-{o['name']}" for o in read_fns[fn_index].get("outputs", [])]
        return []

    # ── Entity step description ────────────────────────────────────────────────

    def _describe_entity_steps(
        self,
        entity_node: dict[str, Any],
        event_name: str,
        contract_name: str,
        contract_id: str,
    ) -> list[dict[str, Any]]:
        data = entity_node["data"]
        entity_name = data.get("name", "UnknownEntity")
        fields = data.get("fields", [])
        entity_id = entity_node["id"]
        is_aggregate = entity_node.get("type") == "aggregateentity"

        steps: list[dict[str, Any]] = []

        # Collect any contract reads needed (deduplicated)
        seen_reads: set[str] = set()

        def collect_reads_for_field(target_handle: str) -> None:
            edge = self._edge_by_target.get((entity_id, target_handle))
            if edge:
                self._collect_contract_read_steps(
                    edge.source, edge.source_handle, steps, seen_reads
                )

        # Scan all field wires for upstream contract reads
        for fld in fields:
            fname = fld.get("name", "")
            if not fname or fld.get("derivedFrom"):
                continue
            handle = "field-id" if fname == "id" else (
                f"field-in-{fname}" if is_aggregate else f"field-{fname}"
            )
            collect_reads_for_field(handle)

        # Determine ID source (both entity types use "field-id" as the handle name)
        id_handle = "field-id"
        id_edge = self._edge_by_target.get((entity_id, id_handle))
        if id_edge:
            id_source = self._describe_value(id_edge.source, id_edge.source_handle, event_name)
        else:
            id_source = "event transaction hash (default — wire an id for stable key)"

        # Entity load / load-or-create step
        steps.append({
            "type":         "entity_load",
            "entity":       entity_name,
            "is_aggregate": is_aggregate,
            "id_source":    id_source,
        })

        # Field writes
        for fld in fields:
            fname = fld.get("name", "")
            if not fname or fname == "id" or fld.get("derivedFrom"):
                continue
            handle = f"field-in-{fname}" if is_aggregate else f"field-{fname}"
            field_edge = self._edge_by_target.get((entity_id, handle))
            if not field_edge:
                if is_aggregate:
                    # Aggregate fields without a wire keep their previous value — show this
                    steps.append({
                        "type":    "field_unchanged",
                        "entity":  entity_name,
                        "field":   fname,
                        "note":    "no wire — keeps previous value (zero on first run)",
                    })
                continue
            source_desc = self._describe_value(
                field_edge.source, field_edge.source_handle, event_name
            )
            steps.append({
                "type":   "field_write",
                "entity": entity_name,
                "field":  fname,
                "source": source_desc,
            })

        # Save
        steps.append({"type": "entity_save", "entity": entity_name})

        return steps

    def _collect_contract_read_steps(
        self,
        node_id: str,
        port_id: str,
        steps: list[dict[str, Any]],
        seen: set[str],
    ) -> None:
        """Recursively walk upstream from (node_id, port_id) and prepend any
        ContractRead nodes found as step entries."""
        node = self._nodes.get(node_id)
        if not node:
            return
        t = node.get("type", "")

        if t == "contractread":
            if node_id in seen:
                return
            seen.add(node_id)

            # Describe this contract read
            data = node["data"]
            fn_index = data.get("fnIndex", 0)
            cr_contract_node = self._nodes.get(data.get("contractNodeId", ""))
            contract_name = cr_contract_node["data"].get("name", "?") if cr_contract_node else "?"

            fn_sig = "?()"
            result_label = "result"
            if cr_contract_node:
                read_fns = cr_contract_node["data"].get("readFunctions", [])
                if fn_index < len(read_fns):
                    fn = read_fns[fn_index]
                    args = ", ".join(i["name"] for i in fn.get("inputs", []))
                    fn_sig = f"{fn['name']}({args})"
                    outs = fn.get("outputs", [])
                    if outs:
                        result_label = ", ".join(o["name"] or f"out{i}" for i, o in enumerate(outs))

            # Resolve bind address
            bind_edge = self._edge_by_target.get((node_id, "bind-address"))
            if bind_edge:
                bind_desc = self._describe_value(bind_edge.source, bind_edge.source_handle, "")
            elif cr_contract_node:
                instances = cr_contract_node["data"].get("instances", [])
                addr = instances[0].get("address", "") if instances else ""
                bind_desc = f'Address.fromString("{addr}")' if addr else "event.address (fallback — add instance address to contract node)"
            else:
                bind_desc = "event.address"

            # Resolve each input argument
            arg_descs: list[str] = []
            if cr_contract_node:
                read_fns = cr_contract_node["data"].get("readFunctions", [])
                if fn_index < len(read_fns):
                    for inp in read_fns[fn_index].get("inputs", []):
                        arg_edge = self._edge_by_target.get((node_id, f"in-{inp['name']}"))
                        if arg_edge:
                            arg_descs.append(
                                f"{inp['name']} = {self._describe_value(arg_edge.source, arg_edge.source_handle, '')}"
                            )
                        else:
                            arg_descs.append(f"{inp['name']} = (unwired)")

            steps.append({
                "type":       "contract_read",
                "label":      f"{contract_name}.{fn_sig}",
                "bind":       bind_desc,
                "args":       arg_descs,
                "result":     result_label,
            })

            # Also walk upstream of this read's inputs (via reverse edge scan)
            for inp_edge in self._edges:
                if inp_edge.target == node_id and inp_edge.target_handle.startswith("in-"):
                    self._collect_contract_read_steps(
                        inp_edge.source, inp_edge.source_handle, steps, seen
                    )
            return

        # For transform nodes, walk their inputs recursively.
        # Guard against cycles by tracking visited (node_id) in seen.
        if t in ("math", "typecast", "strconcat", "conditional"):
            if node_id in seen:
                return
            seen.add(node_id)
            for e in self._edges:
                if e.target == node_id:
                    self._collect_contract_read_steps(e.source, e.source_handle, steps, seen)

    # ── Value describer ────────────────────────────────────────────────────────

    def _describe_value(
        self,
        node_id: str,
        port_id: str,
        event_name: str,
        _seen: frozenset[str] | None = None,
    ) -> str:
        """Return a human-readable description of a source value.

        ``_seen`` tracks node IDs already on the current call stack so that
        cycles in the graph (e.g. math→math→math) do not cause infinite
        recursion.  We use a frozenset so each recursive branch gets its own
        immutable copy and sibling branches don't pollute each other.
        """
        if _seen is None:
            _seen = frozenset()
        if node_id in _seen:
            return "(cycle)"
        _seen = _seen | {node_id}

        node = self._nodes.get(node_id)
        if not node:
            return "(missing source)"
        t = node.get("type", "")
        data = node["data"]

        # Contract node
        if t == "contract":
            contract_name = data.get("name", "?")
            if port_id in _IMPLICIT_LABELS:
                label = _IMPLICIT_LABELS[port_id]
                return f"{contract_name} {label}"
            if port_id == "implicit-instance-address":
                instances = data.get("instances", [])
                addr = instances[0].get("address", "0x0") if instances else "0x0"
                return f'{contract_name} deployed address ({addr})'
            if port_id.startswith("implicit-"):
                rest = port_id[len("implicit-"):]
                return f"{contract_name} {rest.replace('-', '.')}"
            if port_id.startswith("event-"):
                # Port IDs: "event-{EventName}-{paramName}" or "event-{EventName}"
                # Strip the "event-" prefix then split on the first "-" to isolate
                # the event name from a potentially hyphenated param name.
                rest = port_id[len("event-"):]
                if "-" in rest:
                    ev, param = rest.split("-", 1)
                    return f"{ev}.{param} (event parameter)"
                else:
                    return f"{rest} event"
            return f"{contract_name}.{port_id}"

        # Math node
        if t == "math":
            op = data.get("operation", "add")
            op_label = _MATH_OP_LABELS.get(op, op)
            left_edge  = self._edge_by_target.get((node_id, "left"))
            right_edge = self._edge_by_target.get((node_id, "right"))
            left_desc  = self._describe_value(left_edge.source, left_edge.source_handle, event_name, _seen) if left_edge else "0"
            right_desc = self._describe_value(right_edge.source, right_edge.source_handle, event_name, _seen) if right_edge else "0"
            return f"({left_desc} {op_label} {right_desc})"

        # TypeCast node
        if t == "typecast":
            cast_index = data.get("castIndex", 0)
            cast_label = _CAST_LABELS[cast_index] if cast_index < len(_CAST_LABELS) else "cast"
            val_edge = self._edge_by_target.get((node_id, "value"))
            inner = self._describe_value(val_edge.source, val_edge.source_handle, event_name, _seen) if val_edge else "?"
            return f"{inner} {cast_label}"

        # StringConcat node
        if t == "strconcat":
            left_edge  = self._edge_by_target.get((node_id, "left"))
            right_edge = self._edge_by_target.get((node_id, "right"))
            left_desc  = self._describe_value(left_edge.source, left_edge.source_handle, event_name, _seen) if left_edge else '""'
            right_desc = self._describe_value(right_edge.source, right_edge.source_handle, event_name, _seen) if right_edge else '""'
            return f'concat({left_desc}, {right_desc})'

        # Conditional node
        if t == "conditional":
            val_edge  = self._edge_by_target.get((node_id, "value"))
            cond_edge = self._edge_by_target.get((node_id, "condition"))
            val_desc  = self._describe_value(val_edge.source, val_edge.source_handle, event_name, _seen) if val_edge else "?"
            cond_desc = self._describe_value(cond_edge.source, cond_edge.source_handle, event_name, _seen) if cond_edge else "?"
            return f"{val_desc} (if {cond_desc})"

        # ContractRead node
        if t == "contractread":
            fn_index = data.get("fnIndex", 0)
            cr_contract = self._nodes.get(data.get("contractNodeId", ""))
            if cr_contract:
                read_fns = cr_contract["data"].get("readFunctions", [])
                if fn_index < len(read_fns):
                    fn = read_fns[fn_index]
                    cr_name = cr_contract["data"].get("name", "?")
                    return f"result of {cr_name}.{fn['name']}()"
            return "contract read result"

        # AggregateEntity output ports
        if t == "aggregateentity":
            entity_name = data.get("name", "?")
            if port_id.startswith("field-prev-"):
                field_name = port_id[len("field-prev-"):]
                return f"previous {entity_name}.{field_name}"
            if port_id == "field-out-id":
                return f"{entity_name} stable ID"

        return f"{t}.{port_id}"


# ── Public function ────────────────────────────────────────────────────────────

def simulate_graph(visual_config: dict[str, Any]) -> dict[str, Any]:
    """Entry point: returns a structured simulation description dict."""
    return GraphSimulator(visual_config).simulate()
