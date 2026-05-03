"""Graph compiler: visual graph → AssemblyScript event handler code.

Takes the ``visual-config.json`` node/edge graph and produces working
AssemblyScript mapping files (one per contract type), ready for
``graph build``.

Algorithm (per event handler):
  1. Find all Entity nodes that have at least one incoming edge from this event.
  2. For each Entity node, topologically traverse its dependency graph:
       - Follow edges backwards through Math / TypeCast / StringConcat /
         Conditional / ContractRead nodes to event params or implicit ports.
  3. Emit variable declarations in dependency order.
  4. Emit entity load-or-create + field assignments.
  5. Wrap in the standard handler boilerplate.

Port ID conventions (must match the React nodes):
  Contract node output:  "event-{EventName}"  |  "read-{FnName}"
  Event params:          emitted inline inside the handler as event.params.{name}
  Entity fields:         "field-{name}"  (target handles on EntityNode)
  Math ports:            "left", "right" (target) / "result" (source)
  TypeCast ports:        "value" (target) / "result" (source)
  StringConcat ports:    "left", "right" (target) / "result" (source)
  Conditional ports:     "condition", "value" (target) / "value-out" (source)
  ContractRead ports:    "in-{argName}" (target) / "out-{retName}" (source)
"""

from __future__ import annotations

import logging
import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from subgraph_wizard.generate.graph_utils import Edge, build_entity_name_map  # noqa: F401 — re-exported for backward compat

logger = logging.getLogger(__name__)

# ── Data structures ───────────────────────────────────────────────────────────
# Edge is imported from graph_utils and re-exported above.


@dataclass
class CompiledHandler:
    """One AssemblyScript event handler function."""
    contract_type: str
    event_name: str
    event_signature: str
    handler_name: str
    body: str            # full function body (indented, no outer braces)


@dataclass
class CompilerOutput:
    """Output for one contract type."""
    contract_type: str
    handlers: list[CompiledHandler] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Render the full AssemblyScript mapping file."""
        lines: list[str] = []

        # Imports
        seen = set()
        for imp in self.imports:
            if imp not in seen:
                lines.append(imp)
                seen.add(imp)

        if lines:
            lines.append("")

        # Handlers
        for h in self.handlers:
            lines.append(
                f"export function {h.handler_name}(event: {h.event_name}Event): void {{"
            )
            lines.append(h.body)
            lines.append("}")
            lines.append("")

        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _handler_name(event_name: str) -> str:
    if not event_name:
        return "handleUnknownEvent"
    return f"handle{event_name[0].upper()}{event_name[1:]}"


def _var_name(node_id: str, port_id: str) -> str:
    """Stable variable name for a (node, port) pair."""
    safe_node = node_id.replace("-", "_")
    safe_port = port_id.replace("-", "_")
    return f"_{safe_node}__{safe_port}"


def _types_compatible(field_type: str, param_graph_type: str) -> bool:
    """Return True when a ``param_graph_type`` value can be directly assigned
    to an entity field declared as ``field_type`` in AssemblyScript.

    Exact match is always compatible.  Beyond that, The Graph's AssemblyScript
    runtime defines ``Address extends Bytes``, so an Address event param can be
    stored in a Bytes entity field without an explicit cast.  Any other
    cross-type combination must go through a TypeCast node with an explicit wire.
    """
    # Normalise: strip trailing "!" non-null marker (doesn't affect AS types)
    norm_field = field_type.rstrip("!").strip()
    norm_param = param_graph_type.rstrip("!").strip()
    if norm_field == norm_param:
        return True
    # Address extends Bytes in AS: Address param → Bytes field is valid
    if norm_param == "Address" and norm_field == "Bytes":
        return True
    return False


def _event_param_expr(port_id: str) -> str:
    """
    Convert an event output port id to an AssemblyScript expression.
    Port IDs on Event nodes (auto-spawned from ContractNode) look like:
      event-Transfer-from  →  event.params.from
      event-Transfer-value →  event.params.value
    Implicit ports:
      implicit-address     →  event.address
      implicit-block-number→  event.block.number
      implicit-block-timestamp → event.block.timestamp
      implicit-tx-hash     →  event.transaction.hash
    Trigger-only ports (2-part, no param name, e.g. "event-Deposit"):
      These carry no value — fall back to the transaction hash as a safe
      unique-per-event default.  The user should wire an implicit or param
      port instead for meaningful IDs.
    """
    if port_id.startswith("implicit-"):
        rest = port_id[len("implicit-"):]
        mapping = {
            "address":         "event.address",
            "block-number":    "event.block.number",
            "block-timestamp": "event.block.timestamp",
            "tx-hash":         "event.transaction.hash",
        }
        return mapping.get(rest, f"event.{rest}")
    # event-{EventName}-{paramName}
    parts = port_id.split("-", 2)
    if len(parts) == 3:
        return f"event.params.{parts[2]}"
    # Trigger port (event-{EventName}, 2 parts) — no meaningful value.
    # Return the tx hash as a safe per-event unique identifier.
    logger.warning(
        "Trigger port %r wired as a value source; using event.transaction.hash as fallback. "
        "Wire an implicit-* or event-{Name}-{param} port for a stable ID.",
        port_id,
    )
    return "event.transaction.hash.toHexString()"


# ── Core compiler ──────────────────────────────────────────────────────────────


class GraphCompiler:
    """Compile a visual graph config into AssemblyScript mapping files."""

    def __init__(self, visual_config: dict[str, Any]) -> None:
        self._config = visual_config
        self._nodes: dict[str, dict[str, Any]] = {
            n["id"]: n for n in visual_config.get("nodes", [])
        }
        raw_edges = visual_config.get("edges", [])
        self._edges: list[Edge] = [
            Edge(
                id=e["id"],
                source=e["source"],
                source_handle=e.get("sourceHandle", ""),
                target=e["target"],
                target_handle=e.get("targetHandle", ""),
            )
            for e in raw_edges
        ]
        # Index: (target_node_id, target_handle) → Edge
        self._edge_by_target: dict[tuple[str, str], Edge] = {
            (e.target, e.target_handle): e for e in self._edges
        }
        # Index: source_node_id → list[Edge]
        self._edges_from: dict[str, list[Edge]] = defaultdict(list)
        for e in self._edges:
            self._edges_from[e.source].append(e)
        # Resolved entity type names (deduplication via contract-name prefix)
        self._entity_name_map: dict[str, str] = build_entity_name_map(
            visual_config.get("nodes", []),
            raw_edges,
        )
        # Build contract-type → first-instance address lookup from the Networks
        # tab config so that implicit-instance-address can fall back to the
        # Networks-panel address when the ContractNode's inline address is empty.
        self._network_address_by_type: dict[str, str] = {}
        for net_entry in visual_config.get("networks", []):
            for ct, ct_info in net_entry.get("contracts", {}).items():
                if ct not in self._network_address_by_type:
                    instances = ct_info.get("instances", [])
                    if instances:
                        addr = instances[0].get("address", "").strip()
                        if addr:
                            self._network_address_by_type[ct] = addr

    # ── Public API ─────────────────────────────────────────────────────────────

    def compile(self) -> dict[str, CompilerOutput]:
        """Compile the full graph. Returns {contract_type: CompilerOutput}."""
        outputs: dict[str, CompilerOutput] = {}

        contract_nodes = [
            n for n in self._nodes.values() if n.get("type") == "contract"
        ]

        for contract_node in contract_nodes:
            data = contract_node["data"]
            contract_type = data.get("name", "")
            if not contract_type:
                continue

            out = CompilerOutput(contract_type=contract_type)
            events = data.get("events", [])
            for ev in events:
                handler = self._compile_handler(
                    contract_node=contract_node,
                    event=ev,
                    out=out,
                )
                if handler:
                    out.handlers.append(handler)

            # Only import event types that have generated handler functions.
            # Unused imports don't cause errors but cause unnecessary noise.
            handled_names = {h.event_name for h in out.handlers}
            out.imports += self._base_imports(contract_type, events, handled_names)

            outputs[contract_type] = out

        return outputs

    # ── Per-handler compilation ────────────────────────────────────────────────

    def _compile_handler(
        self,
        contract_node: dict[str, Any],
        event: dict[str, Any],
        out: CompilerOutput,
    ) -> CompiledHandler | None:
        """Compile one event handler. Returns None if no entities are wired."""
        event_name = event.get("name", "")
        if not event_name:
            logger.warning("Skipping event with no name")
            return None
        event_port_id = f"event-{event_name}"
        contract_id = contract_node["id"]
        contract_type = contract_node["data"]["name"]

        # Find entity nodes that have edges coming (directly or transitively)
        # from this event's output port on this contract node.
        # We do this by finding all edges leaving the event port.
        entity_targets: list[dict[str, Any]] = []
        for edge in self._edges_from.get(contract_id, []):
            if edge.source_handle == event_port_id:
                target_node = self._nodes.get(edge.target)
                if target_node and target_node.get("type") in ("entity", "aggregateentity"):
                    entity_targets.append(target_node)

        # Also collect entity nodes reachable through transform nodes
        # (math, typecast, strconcat, conditional, contractread)
        reachable_entities = self._find_reachable_entities(contract_id, event_port_id)

        all_entities = {n["id"]: n for n in entity_targets}
        all_entities.update(reachable_entities)

        # Also collect entities that declared this event in their
        # triggerEvents checklist (the no-wire multi-event trigger mechanism).
        # Applies to both aggregateentity (load-or-update) and entity (new record per event).
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
            logger.debug(
                f"No entities wired to {contract_type}.{event_name} — skipping handler"
            )
            return None

        # Build the handler body — aggregates first (history entities depend on prev_ vars)
        body_lines: list[str] = []

        sorted_entities = sorted(
            all_entities.values(),
            key=lambda n: 0 if n.get("type") == "aggregateentity" else 1,
        )

        # Share declared_vars across ALL entity blocks in this handler so that
        # transform nodes (math, contractread, etc.) referenced by multiple entities
        # only emit their `let` declaration once — preventing duplicate-variable errors
        # in the AssemblyScript compiler.
        handler_declared_vars: set[str] = set()

        for entity_node in sorted_entities:
            if entity_node.get("type") == "aggregateentity":
                entity_lines, extra_imports = self._compile_aggregate_entity_block(
                    entity_node=entity_node,
                    event_name=event_name,
                    contract_type=contract_type,
                    contract_id=contract_id,
                    declared_vars=handler_declared_vars,
                )
            else:
                entity_lines, extra_imports = self._compile_entity_block(
                    entity_node=entity_node,
                    event_name=event_name,
                    event_params=event.get("params", []),
                    contract_type=contract_type,
                    contract_id=contract_id,
                    declared_vars=handler_declared_vars,
                )
            body_lines.extend(entity_lines)
            out.imports.extend(extra_imports)

        body = textwrap.indent("\n".join(body_lines), "  ")

        sig = event.get("signature", f"{event_name}()")
        # Normalise: strip "indexed " keyword from signature for the yaml entry.
        # Use re.sub with a word boundary so parameter names that happen to
        # contain "indexed" as a substring (e.g. "indexedValue") are untouched.
        sig_clean = re.sub(r'\bindexed\s+', '', sig)

        return CompiledHandler(
            contract_type=contract_type,
            event_name=event_name,
            event_signature=sig_clean,
            handler_name=_handler_name(event_name),
            body=body,
        )

    def _find_reachable_entities(
        self,
        start_node_id: str,
        start_port_id: str,
    ) -> dict[str, dict[str, Any]]:
        """BFS from start_node:start_port to find all downstream entity nodes."""
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
                t_type = target.get("type", "")
                if t_type in ("entity", "aggregateentity"):
                    found[target["id"]] = target
                elif t_type in ("math", "typecast", "strconcat", "conditional", "contractread"):
                    # Follow through transform node outputs
                    for out_port in self._transform_output_ports(target):
                        queue.append((target["id"], out_port))

        return found

    def _transform_output_ports(self, node: dict[str, Any]) -> list[str]:
        t = node.get("type", "")
        if t in ("math", "typecast", "strconcat"):
            return ["result"]
        if t == "conditional":
            return ["value-out"]
        if t == "contractread":
            fn_index = node["data"].get("fnIndex", 0)
            contract_node_id = node["data"].get("contractNodeId", "")
            contract_node = self._nodes.get(contract_node_id)
            if contract_node:
                read_fns = contract_node["data"].get("readFunctions", [])
                if fn_index < len(read_fns):
                    return [f"out-{o['name']}" for o in read_fns[fn_index].get("outputs", [])]
        return []

    # ── Entity block ───────────────────────────────────────────────────────────

    def _compile_entity_block(
        self,
        entity_node: dict[str, Any],
        event_name: str,
        contract_type: str,
        contract_id: str,
        declared_vars: set[str] | None = None,
        event_params: list[dict[str, Any]] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Emit lines for one entity load/create + field assignments.

        ``declared_vars`` is shared across all entity blocks in the same handler
        so that transform nodes (math, contractread, etc.) shared by multiple
        entities only emit their ``let`` declaration once.

        ``event_params`` is the list of event parameter dicts (from the ABI
        parse result).  When a field has no incoming edge but its name matches
        an event parameter name, the field is auto-filled from
        ``event.params.{fieldName}`` (documented in the README: "Unwired Entity
        field ports are filled automatically from the event parameter of the
        same name.").
        """
        data = entity_node["data"]
        entity_id = entity_node["id"]
        # Use resolved (possibly prefixed) name so it matches schema.graphql
        entity_name = self._entity_name_map.get(entity_id, data.get("name", "UnknownEntity"))
        fields: list[dict[str, Any]] = data.get("fields", [])

        lines: list[str] = []
        extra_imports: list[str] = []
        if declared_vars is None:
            declared_vars = set()

        # Build a set of event param names for auto-fill matching
        event_param_names: set[str] = {
            p["name"] for p in (event_params or []) if p.get("name")
        }

        # ── Collect dependency lines first ──
        dep_lines: list[str] = []

        for fld in fields:
            field_name = fld.get("name", "")
            if not field_name:
                continue
            target_handle = f"field-{field_name}"
            incoming = self._edge_by_target.get((entity_id, target_handle))
            if not incoming:
                continue

            value_expr, dep_stmts, dep_imports = self._resolve_value(
                source_node_id=incoming.source,
                source_handle=incoming.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            dep_lines.extend(dep_stmts)
            extra_imports.extend(dep_imports)

        lines.extend(dep_lines)

        safe_name = entity_name if entity_name else "UnknownEntity"
        # Suffix with "Entity" so the local variable never shadows the schema class
        # (e.g. entity named "tvl" → local var "tvlEntity").
        var = f"{safe_name[0].lower()}{safe_name[1:]}Entity"

        # ── Stable ID — emit dep statements before the load call ──
        # Auto-fill: if id field is not wired and there's a single event param,
        # use the tx hash + log index as default (stable per-event ID).
        id_expr = "event.transaction.hash.toHexString()"
        id_edge = self._edge_by_target.get((entity_id, "field-id"))
        if id_edge:
            id_expr, id_dep_stmts, id_dep_imports = self._resolve_value(
                source_node_id=id_edge.source,
                source_handle=id_edge.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            lines.extend(id_dep_stmts)
            extra_imports.extend(id_dep_imports)

        lines.append(f'let {var} = {safe_name}.load({id_expr})')
        lines.append(f"if ({var} == null) {{")
        lines.append(f"  {var} = new {safe_name}({id_expr})")
        lines.append("}")

        # ── Field assignments ──
        for fld in fields:
            field_name = fld.get("name", "")
            if field_name == "id" or not field_name:
                continue
            # Skip @derivedFrom fields — they are virtual reverse relations
            if fld.get("derivedFrom"):
                continue
            target_handle = f"field-{field_name}"
            incoming = self._edge_by_target.get((entity_id, target_handle))
            if incoming:
                # Explicit wire: use the resolved value
                value_expr, _, _ = self._resolve_value(
                    source_node_id=incoming.source,
                    source_handle=incoming.source_handle,
                    contract_type=contract_type,
                    contract_id=contract_id,
                    declared_vars=declared_vars,
                )
                src_type = (self._nodes.get(incoming.source) or {}).get("type")
                if src_type == "conditional":
                    # Wrap assignment in the per-field guard so that only THIS
                    # field is skipped when the condition is false — other entity
                    # blocks and their save() calls are unaffected.
                    cond_var = _var_name(incoming.source, "cond")
                    lines.append(f"if ({cond_var}) {{")
                    lines.append(f"  {var}.{field_name} = {value_expr}")
                    lines.append("}")
                else:
                    lines.append(f"{var}.{field_name} = {value_expr}")
            elif field_name in event_param_names:
                # Auto-fill: field name matches an event parameter.
                # Types must match — if they don't we raise immediately rather
                # than silently producing a null field in the deployed subgraph.
                event_param = next(
                    (p for p in (event_params or []) if p.get("name") == field_name),
                    None,
                )
                if event_param:
                    param_graph_type = event_param.get("graph_type", "")
                    field_type = fld.get("type", "")
                    if _types_compatible(field_type, param_graph_type):
                        logger.debug(
                            "Auto-filling %s.%s from event.params.%s",
                            entity_name, field_name, field_name,
                        )
                        lines.append(f"{var}.{field_name} = event.params.{field_name}")
                    else:
                        raise ValueError(
                            f"Auto-fill type mismatch in entity '{entity_name}', "
                            f"field '{field_name}':\n"
                            f"  Entity field type : {field_type}\n"
                            f"  Event param type  : {param_graph_type}\n"
                            f"\n"
                            f"Fix: change the entity field type to '{param_graph_type}', "
                            f"or draw an explicit wire (with a TypeCast node if a "
                            f"conversion is needed)."
                        )

        lines.append(f"{var}.save()")
        lines.append("")

        return lines, extra_imports

    # ── Aggregate entity block ────────────────────────────────────────────────

    # Default zero values by Graph type (used for load-or-create initialisation)
    _ZERO_BY_TYPE: dict[str, str] = {
        "BigInt":     "BigInt.fromI32(0)",
        "Int":        "0",
        "BigDecimal": "BigDecimal.fromString('0')",
        "String":     '""',
        "ID":         '""',
        "Bytes":      'Bytes.fromHexString("")',
        "Address":    'Address.fromString("0x0000000000000000000000000000000000000000")',
        "Boolean":    "false",
    }

    def _is_reachable_from_event(
        self,
        source_node_id: str,
        source_handle: str,
        contract_id: str,
        event_name: str,
    ) -> bool:
        """Return True if (source_node_id, source_handle) is reachable from or
        is compatible with the given event context.

        A field-in wire is "reachable" when its source is NOT an event-param
        port that belongs to a *different* event on the same (or another)
        contract node.  Sources that are implicit ports, math/typecast/etc.
        intermediate nodes, or ContractRead outputs are always considered
        reachable (they don't carry event-specific param names).

        The check is intentionally conservative: we only skip wires whose
        immediate source handle names a concrete event param from a different
        event.  Transitive upstream dependencies through transform nodes are not
        inspected — those nodes read from whatever is wired into them, which may
        itself already be event-specific.
        """
        source_node = self._nodes.get(source_node_id)
        if not source_node:
            return True  # missing node — let the compiler emit a comment

        node_type = source_node.get("type", "")

        if node_type == "contract":
            # Event-param ports: "event-{EventName}-{paramName}"
            if source_handle.startswith("event-") and not source_handle.startswith("implicit-"):
                parts = source_handle.split("-", 2)
                if len(parts) >= 2:
                    wired_event = parts[1]
                    # If the port is for a different event, skip it in this handler
                    if wired_event != event_name:
                        return False
            # implicit-* ports and read-* ports are always compatible
            return True

        # Transform nodes (math, typecast, strconcat, conditional, contractread)
        # and aggregateentity prev/id ports are always considered reachable —
        # they may themselves depend on event params, but we don't recurse here.
        return True

    def _compile_aggregate_entity_block(
        self,
        entity_node: dict[str, Any],
        event_name: str,
        contract_type: str,
        contract_id: str,
        declared_vars: set[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Emit lines for an aggregate entity: load-or-create with zero-init,
        previous-value captures, new-value writes, and save.

        Left handles:  field-id (stable key), field-in-{name} (new value)
        Right handles: field-prev-{name}       (value before update)

        When an aggregate is triggered via the ``triggerEvents`` checklist from
        an event that is *different* from the event that supplies some
        ``field-in-*`` wires, those incompatible field wires are silently
        skipped.  The aggregate is still loaded-or-created and saved, which is
        the intended behaviour for multi-event aggregates (e.g., ``totalTVL``
        updated on both Deposit and Withdraw, with each event supplying its own
        field wire).

        ``declared_vars`` is shared across all entity blocks in the same handler
        so that transform nodes shared by multiple entities only emit their
        ``let`` declaration once.
        """
        data = entity_node["data"]
        entity_id = entity_node["id"]
        # Use resolved (possibly prefixed) name so it matches schema.graphql
        entity_name = self._entity_name_map.get(entity_id, data.get("name", "UnknownEntity"))
        fields: list[dict[str, Any]] = data.get("fields", [])

        lines: list[str] = []
        extra_imports: list[str] = []
        if declared_vars is None:
            declared_vars = set()

        non_id_fields = [
            f for f in fields
            if f.get("name") and f.get("name") != "id"
            and not f.get("derivedFrom")  # skip @derivedFrom virtual reverse relations
        ]

        # ── Dependency preamble ──
        # Only resolve dependencies for field-in wires that are compatible with
        # the current event context.
        dep_lines: list[str] = []
        for fld in non_id_fields:
            field_name = fld["name"]
            in_handle = f"field-in-{field_name}"
            incoming = self._edge_by_target.get((entity_id, in_handle))
            if not incoming:
                continue
            if not self._is_reachable_from_event(
                incoming.source, incoming.source_handle, contract_id, event_name
            ):
                continue
            _, dep_stmts, dep_imports = self._resolve_value(
                source_node_id=incoming.source,
                source_handle=incoming.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            dep_lines.extend(dep_stmts)
            extra_imports.extend(dep_imports)
        lines.extend(dep_lines)

        safe_name = entity_name if entity_name else "UnknownEntity"
        # Suffix with "Entity" to guarantee the local variable never shadows the
        # schema class (e.g. entity named "tvl" → local var "tvlEntity").
        var = f"{safe_name[0].lower()}{safe_name[1:]}Entity"
        var_id = f"{var}Id"

        # ── Stable ID — emit dep statements (e.g. strconcat declarations) ──
        id_edge = self._edge_by_target.get((entity_id, "field-id"))
        if id_edge:
            id_expr, id_dep_stmts, id_dep_imports = self._resolve_value(
                source_node_id=id_edge.source,
                source_handle=id_edge.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            lines.extend(id_dep_stmts)
            extra_imports.extend(id_dep_imports)
        else:
            id_expr = "event.transaction.hash.toHexString()"

        # ── Load-or-create with zero initialisation ──
        lines.append(f"let {var_id} = {id_expr}")
        lines.append(f"let {var} = {safe_name}.load({var_id})")
        lines.append(f"if ({var} == null) {{")
        lines.append(f"  {var} = new {safe_name}({var_id})")
        for fld in non_id_fields:
            field_name = fld["name"]
            field_type = fld.get("type", "String")
            zero = self._ZERO_BY_TYPE.get(field_type, '""')
            lines.append(f"  {var}.{field_name} = {zero}")
        lines.append("}")

        # ── Capture previous values ──
        for fld in non_id_fields:
            field_name = fld["name"]
            lines.append(f"let {var}_prev_{field_name} = {var}.{field_name}")

        # ── Write new values ──
        # Only write fields whose wire source is reachable from the current event.
        for fld in non_id_fields:
            field_name = fld["name"]
            in_handle = f"field-in-{field_name}"
            incoming = self._edge_by_target.get((entity_id, in_handle))
            if not incoming:
                continue
            if not self._is_reachable_from_event(
                incoming.source, incoming.source_handle, contract_id, event_name
            ):
                continue
            value_expr, _, _ = self._resolve_value(
                source_node_id=incoming.source,
                source_handle=incoming.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            src_type = (self._nodes.get(incoming.source) or {}).get("type")
            if src_type == "conditional":
                # Per-field conditional guard — only this field is skipped when
                # condition is false; the entity is still created and saved.
                cond_var = _var_name(incoming.source, "cond")
                lines.append(f"if ({cond_var}) {{")
                lines.append(f"  {var}.{field_name} = {value_expr}")
                lines.append("}")
            else:
                lines.append(f"{var}.{field_name} = {value_expr}")

        lines.append(f"{var}.save()")
        lines.append("")
        return lines, extra_imports

    # ── Value resolver ─────────────────────────────────────────────────────────

    # BigInt AssemblyScript operator names
    _BIGINT_OPS = {
        "add": "plus",
        "subtract": "minus",
        "multiply": "times",
        "divide": "div",
        "mod": "mod",
        "pow": "pow",
    }

    # TypeCast code templates (use {v} as placeholder for the input expression)
    _CAST_TEMPLATES = [
        "{v}.toI32()",
        "{v}.toString()",
        "{v}.toHexString()",
        "Address.fromBytes({v})",
        "Bytes.fromHexString({v})",
        "{v}.toHexString()",
        "{v} as Bytes",
    ]

    def _resolve_value(
        self,
        source_node_id: str,
        source_handle: str,
        contract_type: str,
        contract_id: str,
        declared_vars: set[str],
    ) -> tuple[str, list[str], list[str]]:
        """
        Resolve a (source_node, source_handle) pair to an AS expression.

        Returns:
          (expression, dependency_statements, extra_imports)
        """
        source_node = self._nodes.get(source_node_id)
        if not source_node:
            return ("/* missing node */", [], [])

        node_type = source_node.get("type", "")
        data = source_node["data"]

        # ── Contract node — event port or read-function port ───────────────────
        if node_type == "contract":
            # Event params come from event.params.{name}
            if source_handle.startswith("event-"):
                expr = _event_param_expr(source_handle)
                return (expr, [], [])
            # implicit-instance-address: the configured deployed address of THIS contract node.
            # Unlike implicit-address (= event.address = the event-emitting contract), this
            # resolves to Address.fromString("0x...") using the contract's address field.
            if source_handle == "implicit-instance-address":
                # 1. Check the ContractNode's inline address field (legacy / convenience)
                addr = data.get("address", "").strip()
                # 2. Fall back to legacy instances list inside node data
                if not addr:
                    instances = data.get("instances", [])
                    addr = instances[0].get("address", "") if instances else ""
                # 3. Fall back to the Networks panel config (the recommended entry point)
                if not addr:
                    contract_type_name = data.get("name", "")
                    addr = self._network_address_by_type.get(contract_type_name, "")
                addr = addr or "0x0000000000000000000000000000000000000000"
                return (f'Address.fromString("{addr}")', [], [])
            # Other implicit ports (address, block number/timestamp, tx hash)
            if source_handle.startswith("implicit-"):
                expr = _event_param_expr(source_handle)
                return (expr, [], [])
            # Read-function port: handled via ContractRead node instead
            return (f"/* contract read: {source_handle} */", [], [])

        # ── Implicit ports on EventNode (if we ever split them) ───────────────
        if node_type == "event":
            expr = _event_param_expr(source_handle)
            return (expr, [], [])

        # ── Math node ──────────────────────────────────────────────────────────
        if node_type == "math":
            operation = data.get("operation", "add")
            as_op = self._BIGINT_OPS.get(operation, "plus")

            left_edge = self._edge_by_target.get((source_node_id, "left"))
            right_edge = self._edge_by_target.get((source_node_id, "right"))

            stmts: list[str] = []
            imports: list[str] = []

            left_expr = "BigInt.zero()"
            if left_edge:
                left_expr, s, i = self._resolve_value(
                    left_edge.source, left_edge.source_handle,
                    contract_type, contract_id, declared_vars,
                )
                stmts += s; imports += i

            right_expr = "BigInt.zero()"
            if right_edge:
                right_expr, s, i = self._resolve_value(
                    right_edge.source, right_edge.source_handle,
                    contract_type, contract_id, declared_vars,
                )
                stmts += s; imports += i

            var = _var_name(source_node_id, "result")
            if var not in declared_vars:
                stmts.append(f"let {var} = {left_expr}.{as_op}({right_expr})")
                declared_vars.add(var)

            return (var, stmts, imports)

        # ── TypeCast node ──────────────────────────────────────────────────────
        if node_type == "typecast":
            cast_index = data.get("castIndex", 0)
            template = (
                self._CAST_TEMPLATES[cast_index]
                if cast_index < len(self._CAST_TEMPLATES)
                else "{v}"
            )
            value_edge = self._edge_by_target.get((source_node_id, "value"))
            stmts = []
            imports = []
            inner = "/* no input */"
            if value_edge:
                inner, stmts, imports = self._resolve_value(
                    value_edge.source, value_edge.source_handle,
                    contract_type, contract_id, declared_vars,
                )
            expr = template.replace("{v}", inner)
            var = _var_name(source_node_id, "result")
            if var not in declared_vars:
                stmts.append(f"let {var} = {expr}")
                declared_vars.add(var)
            return (var, stmts, imports)

        # ── StringConcat node ──────────────────────────────────────────────────
        if node_type == "strconcat":
            separator = data.get("separator", "")
            left_edge = self._edge_by_target.get((source_node_id, "left"))
            right_edge = self._edge_by_target.get((source_node_id, "right"))
            stmts = []
            imports = []

            left_expr = '""'
            if left_edge:
                left_expr, s, i = self._resolve_value(
                    left_edge.source, left_edge.source_handle,
                    contract_type, contract_id, declared_vars,
                )
                stmts += s; imports += i

            right_expr = '""'
            if right_edge:
                right_expr, s, i = self._resolve_value(
                    right_edge.source, right_edge.source_handle,
                    contract_type, contract_id, declared_vars,
                )
                stmts += s; imports += i

            if separator:
                concat = f'{left_expr}.concat("{separator}").concat({right_expr})'
            else:
                concat = f"{left_expr}.concat({right_expr})"

            var = _var_name(source_node_id, "result")
            if var not in declared_vars:
                stmts.append(f"let {var} = {concat}")
                declared_vars.add(var)
            return (var, stmts, imports)

        # ── Conditional node ───────────────────────────────────────────────────
        if node_type == "conditional":
            cond_edge = self._edge_by_target.get((source_node_id, "condition"))
            value_edge = self._edge_by_target.get((source_node_id, "value"))
            stmts = []
            imports = []

            cond_expr = "true"
            if cond_edge:
                cond_expr, s, i = self._resolve_value(
                    cond_edge.source, cond_edge.source_handle,
                    contract_type, contract_id, declared_vars,
                )
                stmts += s; imports += i

            # Store the condition in a named local variable.
            # The field-assignment site (entity / aggregate block) detects that
            # the source is a conditional node and wraps just that assignment in
            # "if (cond_var) { ... }" — so that only the specific field is
            # skipped when the condition is false.
            #
            # We deliberately do NOT emit a bare "if (!cond) return" here.
            # An early return would cause save() calls for *other* entities
            # compiled later in the same handler to be silently skipped.
            cond_var = _var_name(source_node_id, "cond")
            if cond_var not in declared_vars:
                stmts.append(f"let {cond_var} = {cond_expr}")
                declared_vars.add(cond_var)

            val_expr = "null"
            if value_edge:
                val_expr, s, i = self._resolve_value(
                    value_edge.source, value_edge.source_handle,
                    contract_type, contract_id, declared_vars,
                )
                stmts += s; imports += i

            return (val_expr, stmts, imports)

        # ── ContractRead node ──────────────────────────────────────────────────
        if node_type == "contractread":
            fn_index = data.get("fnIndex", 0)
            ref_contract_id = data.get("contractNodeId", contract_id)
            ref_contract_node = self._nodes.get(ref_contract_id)

            stmts = []
            imports = []

            if not ref_contract_node:
                return (f"/* missing contract node {ref_contract_id} */", [], [])

            ref_contract_type = ref_contract_node["data"].get("name", contract_type)
            read_fns = ref_contract_node["data"].get("readFunctions", [])

            if fn_index >= len(read_fns):
                return ("/* invalid fn index */", [], [])

            fn = read_fns[fn_index]
            fn_name = fn["name"]

            # Resolve arguments
            arg_exprs: list[str] = []
            for inp in fn.get("inputs", []):
                arg_handle = f"in-{inp['name']}"
                arg_edge = self._edge_by_target.get((source_node_id, arg_handle))
                if arg_edge:
                    arg_expr, s, i = self._resolve_value(
                        arg_edge.source, arg_edge.source_handle,
                        contract_type, contract_id, declared_vars,
                    )
                    stmts += s; imports += i
                    arg_exprs.append(arg_expr)
                else:
                    arg_exprs.append("/* missing arg */")

            # Emit: let contract = RefType.bind(address)
            # Priority:
            #   1. Explicit bind-address wire (user overrides)
            #   2. Selected contract node's first instance address (common case:
            #      calling a different contract than the event-emitter)
            #   3. event.address (fallback: same contract that fired the event)
            contract_var = _var_name(source_node_id, "contract")
            if contract_var not in declared_vars:
                bind_edge = self._edge_by_target.get((source_node_id, "bind-address"))
                if bind_edge:
                    bind_expr, bind_stmts, bind_imports = self._resolve_value(
                        bind_edge.source, bind_edge.source_handle,
                        contract_type, contract_id, declared_vars,
                    )
                    stmts += bind_stmts
                    imports += bind_imports
                else:
                    # Auto-use the selected contract's configured address.
                    # Check direct address field first (new UI), then legacy instances list.
                    ref_data = ref_contract_node["data"]
                    ref_addr = ref_data.get("address", "").strip()
                    if not ref_addr:
                        ref_instances = ref_data.get("instances", [])
                        ref_addr = ref_instances[0].get("address", "") if ref_instances else ""
                    if ref_addr:
                        bind_expr = f'Address.fromString("{ref_addr}")'
                        # Address is already included in _base_imports; no extra import needed.
                    else:
                        # No instance configured — fall back to event.address
                        bind_expr = "event.address"
                stmts.append(
                    f"let {contract_var} = {ref_contract_type}.bind({bind_expr})"
                )
                declared_vars.add(contract_var)

            # Emit the call for the requested output port using the try_ variant
            # so that a reverted contract call does not abort the handler.
            # source_handle is "out-{name}"
            out_name = source_handle[4:] if source_handle.startswith("out-") else source_handle
            result_var = _var_name(source_node_id, f"out_{out_name}")
            if result_var not in declared_vars:
                # Determine a safe default value based on the function's return type.
                outputs = fn.get("outputs", [])
                return_type = outputs[0].get("graph_type", "BigInt") if outputs else "BigInt"
                _TYPE_DEFAULTS: dict[str, str] = {
                    "BigInt":     "BigInt.fromI32(0)",
                    "BigDecimal": 'BigDecimal.fromString("0")',
                    "Int":        "0 as i32",
                    "Bytes":      'Bytes.fromHexString("0x")',
                    "Address":    'Address.fromString("0x0000000000000000000000000000000000000000")',
                    "Boolean":    "false",
                    "String":     '""',
                    "ID":         '""',
                }
                default_val = _TYPE_DEFAULTS.get(return_type, "BigInt.fromI32(0)")
                try_var = _var_name(source_node_id, f"try_{out_name}")
                stmts.append(
                    f"let {try_var} = {contract_var}.try_{fn_name}({', '.join(arg_exprs)})"
                )
                stmts.append(
                    f"let {result_var} = {try_var}.reverted ? {default_val} : {try_var}.value"
                )
                declared_vars.add(result_var)

            return (result_var, stmts, imports)

        # ── Aggregate entity node — prev-value or id output ports ────────────
        if node_type == "aggregateentity":
            agg_name = self._entity_name_map.get(source_node_id, data.get("name", "entity"))
            # Must match the "Entity"-suffixed variable name used in _compile_aggregate_entity_block
            agg_var = f"{agg_name[0].lower()}{agg_name[1:]}Entity"
            if source_handle == "field-out-id":
                return (f"{agg_var}Id", [], [])
            if source_handle.startswith("field-prev-"):
                field_name = source_handle[len("field-prev-"):]
                return (f"{agg_var}_prev_{field_name}", [], [])
            return (f"/* aggregateentity: unrecognised handle {source_handle} */", [], [])

        # ── Fallback ───────────────────────────────────────────────────────────
        return (f"/* unhandled node type: {node_type} */", [], [])

    # ── Import boilerplate ────────────────────────────────────────────────────

    def _base_imports(
        self,
        contract_type: str,
        events: list[dict] | None = None,
        handled_event_names: set[str] | None = None,
    ) -> list[str]:
        """Return the import lines for a contract's mapping file.

        ``handled_event_names`` restricts event-type imports to only those that
        have generated handler functions, preventing unused-import warnings.
        If omitted all events are imported (safe fallback).
        """
        # Use resolved (possibly prefixed) entity type names
        entity_names: list[str] = sorted(set(self._entity_name_map.values()))
        entity_import = (
            f"import {{ {', '.join(entity_names)} }} from '../../generated/schema'"
            if entity_names
            else "import { } from '../../generated/schema'"
        )
        # Import contract class + every event type used as a handler parameter.
        # graph codegen generates event classes named after the event with no suffix
        # (e.g. Deposit, not DepositEvent). Alias each as {Name}Event following the
        # official The Graph convention: import { Transfer as TransferEvent } from '...'
        event_aliases = [
            f"{ev['name']} as {ev['name']}Event"
            for ev in (events or [])
            if ev.get("name") and (
                handled_event_names is None or ev["name"] in handled_event_names
            )
        ]
        abi_symbols = [contract_type] + event_aliases
        abi_import = (
            f"import {{ {', '.join(abi_symbols)} }}"
            f" from '../../generated/{contract_type}/{contract_type}'"
        )
        return [
            abi_import,
            entity_import,
            "import { BigInt, Address, Bytes, BigDecimal } from '@graphprotocol/graph-ts'",
        ]


# ── Entity name resolution ────────────────────────────────────────────────────
# build_entity_name_map is now defined in graph_utils and re-exported at the top
# of this module for backward compatibility.

# ── Convenience entry point ───────────────────────────────────────────────────


def compile_graph(visual_config: dict[str, Any]) -> dict[str, str]:
    """Compile a visual-config.json dict to AssemblyScript source files.

    Args:
        visual_config: Parsed visual-config.json.

    Returns:
        Dict mapping contract_type name → AssemblyScript source string.
    """
    compiler = GraphCompiler(visual_config)
    outputs = compiler.compile()
    return {ct: out.render() for ct, out in outputs.items()}
