"""Ponder compiler: visual graph → TypeScript event handler code (src/index.ts).

Mirrors ``graph_compiler.GraphCompiler`` structurally but emits TypeScript for
the Ponder framework instead of AssemblyScript for The Graph.

Key differences from AssemblyScript output:
  - Event params:    event.params.x     → event.args.x
  - Unique event ID: tx-hash + logIndex → event.id  (built-in)
  - Block timestamp: event.block.timestamp → Number(event.block.timestamp)
  - Log address:     event.address      → event.log.address
  - Math operators:  .plus()/.minus()   → +, -, *, /, %, **
  - Entity insert:   new E(id) + save() → suffix-retry insert loop (avoids UniqueConstraintError)
  - Aggregate upsert:load-or-create     → .onConflictDoUpdate((row) => ({...}))
  - Contract reads:  Contract.bind().try_fn() →
                     context.client.readContract({ abi, address, functionName, args, blockNumber })
"""

from __future__ import annotations

import json
import logging
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from subgraph_wizard.generate.graph_utils import build_entity_name_map, Edge, schema_var as _schema_var
from subgraph_wizard.generate.ponder_config import _slug_to_ponder_chain_name

logger = logging.getLogger(__name__)



def _var_name(node_id: str, port_id: str) -> str:
    """Stable variable name for a (node, port) pair (same convention as GraphCompiler)."""
    safe_node = node_id.replace("-", "_")
    safe_port = port_id.replace("-", "_")
    return f"_{safe_node}__{safe_port}"


def _event_param_expr_ts(port_id: str) -> str:
    """Convert a contract node output port ID to a TypeScript expression.

    Ponder differences vs AssemblyScript:
      event-Transfer-from   → event.args.from
      implicit-address      → event.log.address
      implicit-block-timestamp → Number(event.block.timestamp)
      implicit-tx-hash      → event.transaction.hash
    """
    if port_id.startswith("implicit-"):
        # Normalize: implicit-instance-address is semantically identical to
        # implicit-address (both resolve to the log-emitting contract address).
        # Canonicalise here so downstream code only needs to handle one form.
        if port_id == "implicit-instance-address":
            port_id = "implicit-address"
        rest = port_id[len("implicit-"):]
        mapping = {
            "address":         "event.log.address",
            "block-number":    "event.block.number",
            "block-timestamp": "Number(event.block.timestamp)",
            "tx-hash":         "event.transaction.hash",
        }
        return mapping.get(rest, f"event.{rest}")

    # event-{EventName}-{paramName}
    parts = port_id.split("-", 2)
    if len(parts) == 3:
        return f"event.args.{parts[2]}"

    # Trigger-only port (event-{EventName}) — use built-in event.id
    logger.warning(
        "Trigger port %r wired as a value source in Ponder mode; "
        "using event.id as fallback. Wire an implicit-* or param port for a "
        "meaningful ID.",
        port_id,
    )
    return "event.id"


# ── Ponder type defaults (for aggregate initial-value inserts) ─────────────────

_PONDER_ZERO: dict[str, str] = {
    "BigInt":     "0n",
    "Int":        "0",
    # BigDecimal is stored as TEXT in Ponder (no native decimal column type).
    # Arithmetic on BigDecimal fields (e.g. in Math nodes) produces string
    # concatenation at runtime — use a decimal library (e.g. decimal.js) in
    # your handler if you need numeric operations on these values.
    "BigDecimal": '"0"',
    "String":     '""',
    "ID":         '""',
    "Bytes":      '"0x"',
    "Address":    '"0x0000000000000000000000000000000000000000"',
    "Boolean":    "false",
}


# ── TypeCast templates (Ponder / TypeScript) ────────────────────────────────────
# Index matches the castIndex stored in the TypeCast node data.
# {v} is replaced with the input expression.
_CAST_TEMPLATES_TS: list[str] = [
    "Number({v})",                      # 0: BigInt → Int (number)
    "({v}).toString()",                 # 1: BigInt → String
    "{v}",                              # 2: Bytes → String (already 0x…)
    "{v} as `0x${string}`",            # 3: Bytes → Address (same 0x type)
    "{v} as `0x${string}`",            # 4: String → Bytes
    "{v}",                              # 5: Address → Bytes (same type)
    "{v}",                              # 6: Address → String (already string)
]


class PonderCompiler:
    """Compile a visual graph config into Ponder TypeScript handler files."""

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
        _edge_by_target: dict[tuple[str, str], Edge] = {}
        for _e in self._edges:
            _key = (_e.target, _e.target_handle)
            if _key in _edge_by_target:
                logger.warning(
                    "Multiple edges connect to the same target port (%s → %s). "
                    "Only the last wire will be used; earlier connections are "
                    "silently ignored. Remove the duplicate edge in the canvas.",
                    _e.target,
                    _e.target_handle,
                )
            _edge_by_target[_key] = _e
        self._edge_by_target = _edge_by_target
        self._edges_from: dict[str, list[Edge]] = defaultdict(list)
        for e in self._edges:
            self._edges_from[e.source].append(e)

        self._entity_name_map: dict[str, str] = build_entity_name_map(
            visual_config.get("nodes", []),
            raw_edges,
        )

        # contract_type_name → first configured address (from Networks panel)
        self._network_address_by_type: dict[str, str] = {}
        # contract_type_name → {chain_name → [addr, addr, ...]} (all instances)
        self._instances_by_chain: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for net_entry in visual_config.get("networks", []):
            slug = net_entry.get("network", "").strip()
            chain_name = _slug_to_ponder_chain_name(slug) if slug else ""
            for ct, ct_info in net_entry.get("contracts", {}).items():
                instances = ct_info.get("instances", [])
                if ct not in self._network_address_by_type:
                    if instances:
                        addr = instances[0].get("address", "").strip()
                        if addr:
                            self._network_address_by_type[ct] = addr
                if chain_name:
                    for inst in instances:
                        addr = inst.get("address", "").strip()
                        if addr:
                            self._instances_by_chain[ct][chain_name].append(addr)

    # ── Public API ──────────────────────────────────────────────────────────────

    def compile(self) -> dict[str, str]:
        """Compile the full graph.

        Returns:
            {"src/index.ts": <handler source>} — always exactly one file.
        """
        handler_blocks: list[str] = []
        entity_names_needed: set[str] = set()
        abi_imports_needed: set[str] = set()  # contract type names needing Abi import

        contract_nodes = [
            n for n in self._nodes.values() if n.get("type") == "contract"
        ]

        for contract_node in contract_nodes:
            data = contract_node["data"]
            contract_type = data.get("name", "")
            if not contract_type:
                continue

            events = data.get("events", [])
            for ev in events:
                block, used_entities, used_abis = self._compile_handler(
                    contract_node=contract_node,
                    event=ev,
                )
                if block:
                    handler_blocks.append(block)
                    entity_names_needed.update(used_entities)
                    abi_imports_needed.update(used_abis)

            # Setup handler — emitted when the user enables it on the contract node
            if data.get("hasSetupHandler"):
                block, used_entities, used_abis = self._compile_handler(
                    contract_node=contract_node,
                    event={"name": "setup", "params": []},
                )
                if block:
                    handler_blocks.append(block)
                    entity_names_needed.update(used_entities)
                    abi_imports_needed.update(used_abis)
                else:
                    # No entities wired — emit a minimal stub so the file is valid.
                    # Still import the ABI so the user can call readContract()
                    # inside the stub without hitting a missing-import build error.
                    abi_imports_needed.add(contract_type)
                    handler_blocks.append(
                        f'ponder.on("{contract_type}:setup", async ({{ context }}) => {{\n'
                        f"  // TODO: seed initial state here\n"
                        f"}});\n"
                    )

        # ── Assemble imports ──
        lines: list[str] = ['import { ponder } from "ponder:registry";']

        if entity_names_needed:
            # Sort for determinism
            schema_vars = sorted(_schema_var(n) for n in entity_names_needed)
            lines.append(
                f'import {{ {", ".join(schema_vars)} }} from "ponder:schema";'
            )

        for ct_name in sorted(abi_imports_needed):
            lines.append(f'import {{ {ct_name}Abi }} from "../abis/{ct_name}Abi";')

        lines.append("")
        lines.extend(handler_blocks)

        return {"src/index.ts": "\n".join(lines)}

    # ── Per-handler compilation ─────────────────────────────────────────────────

    def _compile_handler(
        self,
        contract_node: dict[str, Any],
        event: dict[str, Any],
    ) -> tuple[str | None, set[str], set[str]]:
        """Compile one ponder.on handler block.

        Returns:
            (block_source | None, entity_names_used, abi_names_used)
        """
        event_name = event.get("name", "")
        if not event_name:
            return None, set(), set()

        event_port_id = f"event-{event_name}"
        contract_id = contract_node["id"]
        contract_type = contract_node["data"]["name"]

        # ── Find all entity nodes wired to this event ──
        all_entities: dict[str, dict[str, Any]] = {}

        # Direct wires from the event trigger port
        for edge in self._edges_from.get(contract_id, []):
            if edge.source_handle == event_port_id:
                target = self._nodes.get(edge.target)
                if target and target.get("type") in ("entity", "aggregateentity"):
                    all_entities[target["id"]] = target

        # Entities reachable through transform nodes
        all_entities.update(self._find_reachable_entities(contract_id, event_port_id))

        # Entities that declared this event in their triggerEvents checklist
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
            return None, set(), set()

        # ── Build handler body ──
        body_lines: list[str] = []
        used_entity_names: set[str] = set()
        used_abi_names: set[str] = set()
        declared_vars: set[str] = set()

        # Aggregates first (their prev-value vars may feed into entity blocks)
        sorted_entities = sorted(
            all_entities.values(),
            key=lambda n: 0 if n.get("type") == "aggregateentity" else 1,
        )

        event_params = event.get("params", [])
        # Make event_name visible to _resolve_value_ts (used for setup-context checks)
        self._compiling_event_name = event_name

        for entity_node in sorted_entities:
            if entity_node.get("type") == "aggregateentity":
                entity_lines, e_names, a_names = self._compile_aggregate_upsert(
                    entity_node=entity_node,
                    event_name=event_name,
                    contract_type=contract_type,
                    contract_id=contract_id,
                    declared_vars=declared_vars,
                )
            else:
                entity_lines, e_names, a_names = self._compile_entity_insert(
                    entity_node=entity_node,
                    event_name=event_name,
                    event_params=event_params,
                    contract_type=contract_type,
                    contract_id=contract_id,
                    declared_vars=declared_vars,
                )
            body_lines.extend(entity_lines)
            used_entity_names.update(e_names)
            used_abi_names.update(a_names)

        # setup handlers receive only `context`; all others receive `event` too
        params = "{ context }" if event_name == "setup" else "{ event, context }"

        if event_name == "setup":
            # Wrap setup handler body in a per-instance loop so the handler runs
            # once per deployed address per chain, with an independent try/catch
            # per instance so one failing readContract doesn't block the others.
            ct_instances = self._instances_by_chain.get(contract_type, {})
            chain_lines: list[str] = []
            for chain_name, addrs in sorted(ct_instances.items()):
                addr_literals = ", ".join(
                    f'"{a}" as `0x${{string}}`' for a in addrs
                )
                chain_lines.append(f'    {json.dumps(chain_name)}: [{addr_literals}],')
            if chain_lines:
                instances_obj = "{\n" + "\n".join(chain_lines) + "\n  }"
            else:
                instances_obj = "{}"

            inner = textwrap.indent("\n".join(body_lines), "      ")
            body = (
                f"  const __instancesByChain: Record<string, `0x${{string}}`[]> = {instances_obj};\n"
                f"  const __instances = __instancesByChain[context.chain.name] ?? [];\n"
                f"  for (const __address of __instances) {{\n"
                f"    try {{\n"
                f"{inner}\n"
                f"    }} catch (err) {{\n"
                f'      console.warn(`[{contract_type}:setup] handler failed for ${{__address}} on chain ${{context.chain.name}}:`, err);\n'
                f"    }}\n"
                f"  }}"
            )
        else:
            body = textwrap.indent("\n".join(body_lines), "  ")

        block = (
            f'ponder.on("{contract_type}:{event_name}", '
            f'async ({params}) => {{\n'
            f"{body}\n"
            f"}});\n"
        )
        return block, used_entity_names, used_abi_names

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

    # ── Entity insert (regular, immutable) ─────────────────────────────────────

    def _compile_entity_insert(
        self,
        entity_node: dict[str, Any],
        event_name: str,
        event_params: list[dict[str, Any]],
        contract_type: str,
        contract_id: str,
        declared_vars: set[str],
    ) -> tuple[list[str], set[str], set[str]]:
        """Emit ``await context.db.insert(table).values({...})`` for a regular entity."""
        data = entity_node["data"]
        entity_id = entity_node["id"]
        entity_name = self._entity_name_map.get(entity_id, data.get("name", "UnknownEntity"))
        var_name = _schema_var(entity_name)
        fields: list[dict[str, Any]] = data.get("fields", [])

        lines: list[str] = []
        extra_abi_imports: set[str] = set()
        used_entities: set[str] = {entity_name}

        event_param_names: set[str] = {
            p["name"] for p in event_params if p.get("name")
        }

        # ── Preamble: resolve dependency statements ──
        for fld in fields:
            fname = field_name = fld.get("name", "")
            if not fname or fname == "id" or fld.get("derivedFrom"):
                continue
            incoming = self._edge_by_target.get((entity_id, f"field-{fname}"))
            if not incoming:
                continue
            _, dep_stmts, dep_abis = self._resolve_value_ts(
                source_node_id=incoming.source,
                source_handle=incoming.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            lines.extend(dep_stmts)
            extra_abi_imports.update(dep_abis)

        # ── ID expression ──
        # setup has no event object, so default to a static string
        id_expr = '"initial"' if event_name == "setup" else "event.id"
        id_edge = self._edge_by_target.get((entity_id, "field-id"))
        if id_edge:
            id_expr, id_stmts, id_abis = self._resolve_value_ts(
                source_node_id=id_edge.source,
                source_handle=id_edge.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            lines.extend(id_stmts)
            extra_abi_imports.update(id_abis)

        # ── Build values object ──
        # `chain` is auto-injected right after `id` (unless the user already
        # has a field named "chain" in their entity definition).
        user_field_names = {f.get("name", "") for f in fields}
        # Note: values_lines items must NOT have leading spaces — the emit loop
        # below adds its own uniform indentation ("      {vl}").
        values_lines: list[str] = [f"id: {id_expr},"]
        if "chain" not in user_field_names:
            values_lines.append("chain: context.chain.name,")

        for fld in fields:
            fname = fld.get("name", "")
            if fname == "id" or not fname or fld.get("derivedFrom"):
                continue
            incoming = self._edge_by_target.get((entity_id, f"field-{fname}"))
            if incoming:
                val_expr, _, _ = self._resolve_value_ts(
                    source_node_id=incoming.source,
                    source_handle=incoming.source_handle,
                    contract_type=contract_type,
                    contract_id=contract_id,
                    declared_vars=declared_vars,
                )
                src_type = (self._nodes.get(incoming.source) or {}).get("type")
                if src_type == "conditional":
                    # Wrap with conditional guard on the insert.
                    # For required (non-nullable) fields use the type's zero
                    # value as the false-branch fallback; for optional fields
                    # use null so the column stays NULL rather than undefined
                    # (which would violate a NOT NULL constraint at runtime).
                    cond_var = _var_name(incoming.source, "cond")
                    field_required = bool(fld.get("required"))
                    field_type = fld.get("type", "String")
                    fallback = _PONDER_ZERO.get(field_type, "null") if field_required else "null"
                    values_lines.append(f"{fname}: {cond_var} ? {val_expr} : {fallback},")
                else:
                    values_lines.append(f"{fname}: {val_expr},")
            elif fname in event_param_names:
                # Auto-fill: field name matches an event parameter name.
                values_lines.append(f"{fname}: event.args.{fname},")

        # ── Emit ID suffix-retry insert ──
        # If two events in the same block produce the same ID (e.g. both use
        # blockNumber as their primary key), we append "_2", "_3", … until the
        # insert succeeds rather than silently dropping or overwriting the record.
        lines.append(f"{{ const __baseId = {id_expr};")
        lines.append(f"for (let __n = 1; ; __n++) {{")
        lines.append(f"  const __id = __n === 1 ? __baseId : `${{__baseId}}_${{__n}}`;")
        lines.append(f"  try {{")
        lines.append(f"    await context.db.insert({var_name}).values({{")
        for vl in values_lines:
            # Replace the `id: <expr>` line with `id: __id` (the loop variable).
            if vl.strip().startswith("id:"):
                lines.append(f"      id: __id,")
            else:
                lines.append(f"      {vl}")
        lines.append(f"    }});")
        lines.append(f"    break;")
        lines.append(f"  }} catch (__e) {{")
        # constructor.name is unreliable after minification (pnpm start / production
        # builds).  Also check the error message for common unique-constraint strings
        # from pg (code "23505"), SQLite ("UNIQUE constraint failed"), and Drizzle.
        lines.append(f"    {{ const __cn = (__e as any)?.constructor?.name ?? \"\";")
        lines.append(f"      const __em = String((__e as any)?.message ?? \"\");")
        lines.append(f"      const __isUnique = __cn === \"UniqueConstraintError\" ||")
        lines.append(f"        (__e as any)?.code === \"23505\" ||")
        lines.append(f"        __em.toLowerCase().includes(\"unique\");")
        lines.append(f"      if (__isUnique) continue; }}")
        lines.append(f"    throw __e;")
        lines.append(f"  }}")
        lines.append(f"}}}}")
        lines.append("")

        return lines, used_entities, extra_abi_imports

    # ── Aggregate entity upsert ─────────────────────────────────────────────────

    def _is_reachable_from_event(
        self,
        source_node_id: str,
        source_handle: str,
        contract_id: str,
        event_name: str,
        _visited: frozenset[tuple[str, str]] | None = None,
    ) -> bool:
        """Return True if (source_node, source_handle) is reachable from the
        current event without crossing a different event's trigger port.

        The check is recursive: for transform nodes (math, typecast, etc.) we
        inspect every upstream input edge.  If *any* ancestor resolves to a
        contract port whose event name differs from ``event_name``, the whole
        subtree is considered unreachable for this event.

        A visited set guards against cycles in the graph.
        """
        if _visited is None:
            _visited = frozenset()
        key = (source_node_id, source_handle)
        if key in _visited:
            return True  # cycle — assume reachable to avoid infinite recursion
        _visited = _visited | {key}

        source_node = self._nodes.get(source_node_id)
        if not source_node:
            return True
        node_type = source_node.get("type", "")

        # ── Contract node: check whether the port belongs to this event ───────
        if node_type == "contract":
            if source_handle.startswith("event-"):
                parts = source_handle.split("-", 2)
                # parts[1] is the event name embedded in the port id
                if len(parts) >= 2 and parts[1] != event_name:
                    return False
            # implicit-* ports (block, tx, address) are always available
            return True

        # ── Transform nodes: recurse into every input edge ────────────────────
        if node_type in ("math", "typecast", "strconcat", "conditional", "contractread"):
            for in_handle in self._transform_input_handles(source_node, source_handle):
                in_edge = self._edge_by_target.get((source_node_id, in_handle))
                if in_edge and not self._is_reachable_from_event(
                    in_edge.source, in_edge.source_handle,
                    contract_id, event_name, _visited,
                ):
                    return False

        return True

    def _transform_input_handles(
        self, node: dict[str, Any], source_handle: str
    ) -> list[str]:
        """Return the list of target-side input handles for a transform node.

        Used by ``_is_reachable_from_event`` to walk the graph backwards.
        """
        t = node.get("type", "")
        if t == "math":
            return ["left", "right"]
        if t == "typecast":
            return ["value"]
        if t == "strconcat":
            return ["left", "right"]
        if t == "conditional":
            return ["condition", "value"]
        if t == "contractread":
            fn_index = node["data"].get("fnIndex", 0)
            ref_id = node["data"].get("contractNodeId", "")
            ref_node = self._nodes.get(ref_id)
            if ref_node:
                read_fns = ref_node["data"].get("readFunctions", [])
                if fn_index < len(read_fns):
                    fn = read_fns[fn_index]
                    return ["bind-address"] + [
                        f"in-{inp['name']}" for inp in fn.get("inputs", [])
                    ]
        return []

    def _compile_aggregate_upsert(
        self,
        entity_node: dict[str, Any],
        event_name: str,
        contract_type: str,
        contract_id: str,
        declared_vars: set[str],
    ) -> tuple[list[str], set[str], set[str]]:
        """Emit ``context.db.insert(table).values({...}).onConflictDoUpdate(...)``."""
        data = entity_node["data"]
        entity_id = entity_node["id"]
        entity_name = self._entity_name_map.get(entity_id, data.get("name", "UnknownEntity"))
        var_name = _schema_var(entity_name)
        fields: list[dict[str, Any]] = data.get("fields", [])

        lines: list[str] = []
        extra_abi_imports: set[str] = set()
        used_entities: set[str] = {entity_name}

        non_id_fields = [
            f for f in fields
            if f.get("name") and f.get("name") != "id" and not f.get("derivedFrom")
        ]

        # ── Preamble: resolve dependency statements ──
        for fld in non_id_fields:
            fname = fld["name"]
            in_handle = f"field-in-{fname}"
            incoming = self._edge_by_target.get((entity_id, in_handle))
            if not incoming:
                continue
            if not self._is_reachable_from_event(
                incoming.source, incoming.source_handle, contract_id, event_name
            ):
                continue
            _, dep_stmts, dep_abis = self._resolve_value_ts(
                source_node_id=incoming.source,
                source_handle=incoming.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
                row_mode=False,       # for dep stmts, doesn't matter — just collecting side-effects
                row_entity_name=entity_name,
            )
            lines.extend(dep_stmts)
            extra_abi_imports.update(dep_abis)

        # ── ID expression ──
        id_expr = '"global"'
        id_edge = self._edge_by_target.get((entity_id, "field-id"))
        if id_edge:
            id_expr, id_stmts, id_abis = self._resolve_value_ts(
                source_node_id=id_edge.source,
                source_handle=id_edge.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
            )
            lines.extend(id_stmts)
            extra_abi_imports.update(id_abis)

        # ── Build .values({}) (initial values for new records) ──
        # `chain` is auto-injected unless the user already has a field named "chain".
        agg_user_field_names = {f.get("name", "") for f in fields}
        initial_values: list[str] = [f"id: {id_expr}"]
        if "chain" not in agg_user_field_names:
            initial_values.append("chain: context.chain.name")
        for fld in non_id_fields:
            fname = fld["name"]
            field_type = fld.get("type", "BigInt")
            in_handle = f"field-in-{fname}"
            incoming = self._edge_by_target.get((entity_id, in_handle))
            if not incoming or not self._is_reachable_from_event(
                incoming.source, incoming.source_handle, contract_id, event_name
            ):
                # No wire for this event — use zero so the insert always has all cols
                zero = _PONDER_ZERO.get(field_type, "0n")
                initial_values.append(f"{fname}: {zero}")
                continue
            # Resolve with prev=zero (new record, no existing row).
            # Use the shared declared_vars so any ContractRead/Math dependency
            # stmts are emitted into `lines` at most once (via the preamble pass
            # above), and the init_expr just references the already-declared var.
            init_expr, init_stmts, init_abis = self._resolve_value_ts(
                source_node_id=incoming.source,
                source_handle=incoming.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
                row_mode=False,
                row_entity_name=entity_name,
            )
            # Emit any stmts not already covered by the preamble pass.
            lines.extend(init_stmts)
            extra_abi_imports.update(init_abis)
            initial_values.append(f"{fname}: {init_expr}")

        # ── Build .onConflictDoUpdate((row) => ({...})) ──
        update_values: list[str] = []
        if "chain" not in agg_user_field_names:
            update_values.append("chain: context.chain.name")
        for fld in non_id_fields:
            fname = fld["name"]
            in_handle = f"field-in-{fname}"
            incoming = self._edge_by_target.get((entity_id, in_handle))
            if not incoming or not self._is_reachable_from_event(
                incoming.source, incoming.source_handle, contract_id, event_name
            ):
                continue
            # Use shared declared_vars so any dependency stmts (ContractRead, etc.)
            # are emitted into `lines` before the insert call, not discarded.
            update_expr, update_stmts, update_abis = self._resolve_value_ts(
                source_node_id=incoming.source,
                source_handle=incoming.source_handle,
                contract_type=contract_type,
                contract_id=contract_id,
                declared_vars=declared_vars,
                row_mode=True,
                row_entity_name=entity_name,
            )
            lines.extend(update_stmts)
            extra_abi_imports.update(update_abis)
            src_type = (self._nodes.get(incoming.source) or {}).get("type")
            if src_type == "conditional":
                cond_var = _var_name(incoming.source, "cond")
                update_values.append(f"{fname}: {cond_var} ? {update_expr} : row.{fname}")
            else:
                update_values.append(f"{fname}: {update_expr}")

        # ── Emit the db call ──
        initial_str = ", ".join(initial_values)
        if not update_values:
            # No field-in wires — just do a plain insert that ignores conflicts
            lines.append(f"await context.db.insert({var_name}).values({{ {initial_str} }})")
            lines.append("  .onConflictDoNothing();")
        else:
            update_str = ", ".join(update_values)
            lines.append(f"await context.db.insert({var_name}).values({{ {initial_str} }})")
            lines.append(f"  .onConflictDoUpdate((row) => ({{ {update_str} }}));")
        lines.append("")

        return lines, used_entities, extra_abi_imports

    # ── Value resolver (TypeScript) ─────────────────────────────────────────────

    # Ponder math uses native TypeScript operators
    _TS_OPS = {
        "add":      "+",
        "subtract": "-",
        "multiply": "*",
        "divide":   "/",
        "mod":      "%",
        "pow":      "**",
    }

    def _resolve_value_ts(
        self,
        source_node_id: str,
        source_handle: str,
        contract_type: str,
        contract_id: str,
        declared_vars: set[str],
        row_mode: bool = False,
        row_entity_name: str | None = None,
    ) -> tuple[str, list[str], set[str]]:
        """Resolve a (source_node, source_handle) to a TypeScript expression.

        Args:
            source_node_id: ID of the node providing the value.
            source_handle:  Output handle on that node.
            contract_type:  Name of the contract being compiled.
            contract_id:    Node ID of the contract node.
            declared_vars:  Set of already-emitted variable names (for dedup).
            row_mode:       When True, aggregate ``field-prev-*`` refs resolve to
                            ``row.{fieldName}`` instead of the zero literal.
            row_entity_name: Resolved name of the current aggregate entity (for
                            disambiguating ``field-prev-*`` targets).

        Returns:
            (expression, dependency_statements, abi_names_needed)
        """
        source_node = self._nodes.get(source_node_id)
        if not source_node:
            return ("/* missing node */", [], set())

        node_type = source_node.get("type", "")
        data = source_node["data"]

        # ── Contract node ──────────────────────────────────────────────────────
        if node_type == "contract":
            is_setup = getattr(self, "_compiling_event_name", "") == "setup"

            # In setup handlers there is no event object — implicit ports that
            # normally reference event.log.address / event.block.number etc. must
            # be replaced with safe compile-time values.
            if is_setup and source_handle.startswith("implicit-"):
                # Normalise implicit-instance-address → implicit-address
                _sh = "implicit-address" if source_handle == "implicit-instance-address" else source_handle
                if _sh == "implicit-address":
                    # Use the per-instance loop variable so each instance gets its
                    # own address when the handler iterates over all instances.
                    return ("__address", [], set())
                source_handle = _sh
                # block-number, block-timestamp, tx-hash have no equivalent in setup
                return (f"undefined /* {source_handle} unavailable in setup handler */", [], set())

            if source_handle.startswith("event-") or source_handle.startswith("implicit-"):
                expr = _event_param_expr_ts(source_handle)
                return (expr, [], set())
            # ── Direct read-{fn} port wired as a value source ────────────────
            if source_handle.startswith("read-"):
                fn_name = source_handle[len("read-"):]
                ct_name = data.get("name", contract_type)
                read_fns = data.get("readFunctions", [])
                fn = next((f for f in read_fns if f.get("name") == fn_name), None)
                if not fn:
                    return (f"/* unknown read fn: {fn_name} */", [], set())

                # Resolve bind address — in setup handlers use the per-instance
                # loop variable so each iteration reads from its own address.
                if getattr(self, "_compiling_event_name", "") == "setup":
                    bind_expr = "__address"
                else:
                    addr = data.get("address", "").strip()
                    if not addr:
                        instances = data.get("instances", [])
                        addr = instances[0].get("address", "") if instances else ""
                    if not addr:
                        addr = self._network_address_by_type.get(ct_name, "")
                    bind_expr = (
                        f'"{addr}" as `0x${{string}}`'
                        if addr
                        else "event.log.address"
                    )

                stmts: list[str] = []
                abi_names: set[str] = {ct_name}
                var = _var_name(source_node_id, source_handle)
                if var not in declared_vars:
                    stmts.append(f"const {var} = await context.client.readContract({{")
                    stmts.append(f"  abi: {ct_name}Abi,")
                    stmts.append(f"  address: {bind_expr},")
                    stmts.append(f'  functionName: "{fn_name}",')
                    if getattr(self, "_compiling_event_name", "") != "setup":
                        stmts.append(f"  blockNumber: event.block.number,")
                    stmts.append(f"}});")
                    declared_vars.add(var)
                return (var, stmts, abi_names)

            return (f"/* unhandled contract port: {source_handle} */", [], set())

        # ── Math node ──────────────────────────────────────────────────────────
        if node_type == "math":
            operation = data.get("operation", "add")
            op = self._TS_OPS.get(operation, "+")

            left_edge = self._edge_by_target.get((source_node_id, "left"))
            right_edge = self._edge_by_target.get((source_node_id, "right"))

            stmts: list[str] = []
            abi_names: set[str] = set()

            left_expr = "0n"
            if left_edge:
                left_expr, s, a = self._resolve_value_ts(
                    left_edge.source, left_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
                stmts += s; abi_names |= a

            right_expr = "0n"
            if right_edge:
                right_expr, s, a = self._resolve_value_ts(
                    right_edge.source, right_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
                stmts += s; abi_names |= a

            var = _var_name(source_node_id, "result")
            if var not in declared_vars:
                stmts.append(f"const {var} = {left_expr} {op} {right_expr};")
                declared_vars.add(var)

            return (var, stmts, abi_names)

        # ── TypeCast node ──────────────────────────────────────────────────────
        if node_type == "typecast":
            cast_index = data.get("castIndex", 0)
            template = (
                _CAST_TEMPLATES_TS[cast_index]
                if cast_index < len(_CAST_TEMPLATES_TS)
                else "{v}"
            )
            value_edge = self._edge_by_target.get((source_node_id, "value"))
            stmts = []
            abi_names: set[str] = set()
            inner = "/* no input */"
            if value_edge:
                inner, stmts, abi_names = self._resolve_value_ts(
                    value_edge.source, value_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
            expr = template.replace("{v}", inner)
            var = _var_name(source_node_id, "result")
            if var not in declared_vars:
                stmts.append(f"const {var} = {expr};")
                declared_vars.add(var)
            return (var, stmts, abi_names)

        # ── StringConcat node ──────────────────────────────────────────────────
        if node_type == "strconcat":
            separator = data.get("separator", "")
            left_edge = self._edge_by_target.get((source_node_id, "left"))
            right_edge = self._edge_by_target.get((source_node_id, "right"))
            stmts = []
            abi_names: set[str] = set()

            left_expr = '""'
            if left_edge:
                left_expr, s, a = self._resolve_value_ts(
                    left_edge.source, left_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
                stmts += s; abi_names |= a

            right_expr = '""'
            if right_edge:
                right_expr, s, a = self._resolve_value_ts(
                    right_edge.source, right_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
                stmts += s; abi_names |= a

            concat = f"`${{{left_expr}}}{separator}${{{right_expr}}}`"

            var = _var_name(source_node_id, "result")
            if var not in declared_vars:
                stmts.append(f"const {var} = {concat};")
                declared_vars.add(var)
            return (var, stmts, abi_names)

        # ── Conditional node ───────────────────────────────────────────────────
        if node_type == "conditional":
            cond_edge = self._edge_by_target.get((source_node_id, "condition"))
            value_edge = self._edge_by_target.get((source_node_id, "value"))
            stmts = []
            abi_names: set[str] = set()

            cond_expr = "true"
            if cond_edge:
                cond_expr, s, a = self._resolve_value_ts(
                    cond_edge.source, cond_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
                stmts += s; abi_names |= a

            cond_var = _var_name(source_node_id, "cond")
            if cond_var not in declared_vars:
                stmts.append(f"const {cond_var} = {cond_expr};")
                declared_vars.add(cond_var)

            val_expr = "undefined"
            if value_edge:
                val_expr, s, a = self._resolve_value_ts(
                    value_edge.source, value_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
                stmts += s; abi_names |= a

            return (val_expr, stmts, abi_names)

        # ── ContractRead node ──────────────────────────────────────────────────
        if node_type == "contractread":
            fn_index = data.get("fnIndex", 0)
            ref_contract_id = data.get("contractNodeId", contract_id)
            ref_contract_node = self._nodes.get(ref_contract_id)

            stmts = []
            abi_names: set[str] = set()

            if not ref_contract_node:
                return (f"/* missing contract node {ref_contract_id} */", [], set())

            ref_contract_type = ref_contract_node["data"].get("name", contract_type)
            read_fns = ref_contract_node["data"].get("readFunctions", [])

            if fn_index >= len(read_fns):
                return ("/* invalid fn index */", [], set())

            fn = read_fns[fn_index]
            fn_name = fn["name"]

            # Resolve arguments
            arg_exprs: list[str] = []
            for inp in fn.get("inputs", []):
                arg_handle = f"in-{inp['name']}"
                arg_edge = self._edge_by_target.get((source_node_id, arg_handle))
                if arg_edge:
                    arg_expr, s, a = self._resolve_value_ts(
                        arg_edge.source, arg_edge.source_handle,
                        contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                    )
                    stmts += s; abi_names |= a
                    arg_exprs.append(arg_expr)
                else:
                    arg_exprs.append("/* missing arg */")

            # Determine bind address
            bind_edge = self._edge_by_target.get((source_node_id, "bind-address"))
            if bind_edge:
                bind_expr, bind_stmts, bind_abis = self._resolve_value_ts(
                    bind_edge.source, bind_edge.source_handle,
                    contract_type, contract_id, declared_vars, row_mode, row_entity_name,
                )
                stmts += bind_stmts
                abi_names |= bind_abis
            else:
                is_setup = getattr(self, "_compiling_event_name", "") == "setup"
                if is_setup and ref_contract_id == contract_id:
                    # Same contract as the setup handler — use the per-instance
                    # loop variable so each iteration reads from its own address.
                    bind_expr = "__address"
                else:
                    ref_data = ref_contract_node["data"]
                    ref_addr = ref_data.get("address", "").strip()
                    if not ref_addr:
                        ref_instances = ref_data.get("instances", [])
                        ref_addr = ref_instances[0].get("address", "") if ref_instances else ""
                    if ref_addr:
                        bind_expr = f'"{ref_addr}" as `0x${{string}}`'
                    else:
                        bind_expr = "event.log.address"

            abi_names.add(ref_contract_type)

            out_name = source_handle[4:] if source_handle.startswith("out-") else source_handle

            # Detect whether this output is a tuple struct component.  When the
            # read function returns a struct, viem returns a plain JS object; the
            # compiler must emit ``result.fieldName`` rather than ``result``.
            fn_outputs = fn.get("outputs", [])
            out_entry = next(
                (o for o in fn_outputs if o.get("name") == out_name), None
            )
            is_tuple_component = bool(
                out_entry and out_entry.get("is_tuple_component")
            )

            # Tuple components share a single readContract call keyed by the
            # node id (no out_name suffix).  Non-tuple outputs keep the current
            # per-name key so existing canvases are unaffected.
            call_var = (
                _var_name(source_node_id, "out")
                if is_tuple_component
                else _var_name(source_node_id, f"out_{out_name}")
            )
            result_expr = f"{call_var}.{out_name}" if is_tuple_component else call_var

            if call_var not in declared_vars:
                stmts.append(
                    f"const {call_var} = await context.client.readContract({{"
                )
                stmts.append(f"  abi: {ref_contract_type}Abi,")
                stmts.append(f"  address: {bind_expr},")
                stmts.append(f"  functionName: \"{fn_name}\",")
                if arg_exprs:
                    stmts.append(f"  args: [{', '.join(arg_exprs)}],")
                # setup handlers have no event — omit blockNumber so the read
                # uses the latest block at indexing time instead of crashing
                if getattr(self, "_compiling_event_name", "") != "setup":
                    stmts.append(f"  blockNumber: event.block.number,")
                stmts.append(f"}});")
                declared_vars.add(call_var)

            return (result_expr, stmts, abi_names)

        # ── Aggregate entity node — prev-value or id output ports ────────────
        if node_type == "aggregateentity":
            agg_name = self._entity_name_map.get(source_node_id, data.get("name", "entity"))
            if source_handle.startswith("field-prev-"):
                field_name = source_handle[len("field-prev-"):]
                if row_mode:
                    # In onConflictDoUpdate callback — reference row parameter
                    return (f"row.{field_name}", [], set())
                else:
                    # In .values() — use zero value for this field type
                    entity_fields = data.get("fields", [])
                    fld = next((f for f in entity_fields if f.get("name") == field_name), None)
                    field_type = fld.get("type", "BigInt") if fld else "BigInt"
                    zero = _PONDER_ZERO.get(field_type, "0n")
                    return (zero, [], set())
            if source_handle == "field-out-id":
                return (f'/* aggregate id of {agg_name} */', [], set())
            return (f"/* aggregateentity: unrecognised handle {source_handle} */", [], set())

        # ── Fallback ───────────────────────────────────────────────────────────
        return (f"/* unhandled node type: {node_type} */", [], set())


def compile_ponder(visual_config: dict[str, Any]) -> dict[str, str]:
    """Compile the visual graph to Ponder TypeScript files.

    Args:
        visual_config: Parsed visual-config.json dict.

    Returns:
        Dict mapping relative file paths to string content.
        E.g. {"src/index.ts": "import { ponder } from ..."}.
    """
    compiler = PonderCompiler(visual_config)
    return compiler.compile()


def render_abi_ts(contract_name: str, abi: list[dict[str, Any]]) -> str:
    """Convert a JSON ABI list to a TypeScript ``as const`` export.

    Args:
        contract_name: Name of the contract (e.g. "ERC20").
        abi: Parsed ABI list.

    Returns:
        Content of ``abis/{contract_name}Abi.ts``.
    """
    abi_json = json.dumps(abi, indent=2, ensure_ascii=False)
    return f"export const {contract_name}Abi = {abi_json} as const;\n"
