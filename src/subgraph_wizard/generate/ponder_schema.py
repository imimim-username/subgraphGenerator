"""Generate ponder.schema.ts from entity and aggregateentity nodes.

For each entity/aggregateentity node in the visual graph, emits one
``onchainTable(...)`` export.  Field types are mapped from the internal
Graph type system to Ponder's ``t.*`` column helpers.

Type mapping:
  ID         → t.text().primaryKey()
  String     → t.text()
  BigInt     → t.bigint()
  Int        → t.integer()
  Boolean    → t.boolean()
  Bytes      → t.hex()
  Address    → t.hex()
  BigDecimal → t.text()  (with a TODO comment; no native decimal type in Ponder)
  [T!]       → t.text()  (array columns not supported; stored as JSON text)
  OtherEntity→ t.text()  (entity references stored as ID text)

@derivedFrom fields are skipped (virtual reverse relations, not stored columns).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Map from internal Graph type to Ponder column helper expression.
# The ".notNull()" suffix is applied separately when the field is required.
_PONDER_COLUMN: dict[str, str] = {
    "ID":         "t.text()",
    "String":     "t.text()",
    "BigInt":     "t.bigint()",
    "Int":        "t.integer()",
    "Boolean":    "t.boolean()",
    "Bytes":      "t.hex()",
    "Address":    "t.hex()",
    "BigDecimal": "t.text() /* BigDecimal mapped to text; use .toString()/.toFixed() in handlers */",
}

# Set of all known primitive type names
_KNOWN_PRIMITIVES: frozenset[str] = frozenset(_PONDER_COLUMN.keys())


def _schema_var(entity_name: str) -> str:
    """Convert a PascalCase entity name to a camelCase schema variable name.

    Examples:
        Transfer        → transfer
        TVL             → tVL
        AlchemistDeposit→ alchemistDeposit
    """
    if not entity_name:
        return "unknown"
    return entity_name[0].lower() + entity_name[1:]


def _column_expr(field: dict[str, Any], is_id: bool) -> str:
    """Return the Ponder column expression for a single field.

    Args:
        field: Field dict with keys ``name``, ``type``, ``required``, ``derivedFrom``.
        is_id: True when this is the ``id`` field (always primaryKey).

    Returns:
        Column helper string, e.g. ``t.bigint().notNull()``.
    """
    ftype_raw = field.get("type", "String")
    required = bool(field.get("required")) or is_id

    if is_id:
        return "t.text().primaryKey()"

    # List types (e.g. "[BigInt!]") — no native array support in Ponder
    if ftype_raw.startswith("["):
        col = "t.text()"
        suffix = ".notNull()" if required else ""
        return f"{col}{suffix} /* array stored as JSON text */"

    # Known primitive type
    if ftype_raw in _KNOWN_PRIMITIVES:
        col = _PONDER_COLUMN[ftype_raw]
        # BigDecimal comment already embedded; don't double-append notNull inside comment
        if "/* " in col:
            # Strip the comment, add notNull, re-append comment
            method_part, comment_part = col.split("/*", 1)
            method_part = method_part.rstrip()
            suffix = ".notNull()" if required else ""
            return f"{method_part}{suffix} /*{comment_part}"
        suffix = ".notNull()" if required else ""
        return f"{col}{suffix}"

    # Entity reference (field type is another entity name) → store as text ID
    suffix = ".notNull()" if required else ""
    return f"t.text(){suffix} /* ref → {ftype_raw} */"


def render_ponder_schema(visual_config: dict[str, Any]) -> str:
    """Generate the full ponder.schema.ts content from entity nodes.

    Args:
        visual_config: Parsed visual-config.json dict (nodes, edges, ...).

    Returns:
        String content of ponder.schema.ts.
    """
    # Import the entity name resolver so that conflict-prefixed names
    # (e.g. AlchemistV3Deposit) are used consistently.
    from subgraph_wizard.generate.graph_compiler import build_entity_name_map

    nodes: list[dict[str, Any]] = visual_config.get("nodes", [])
    edges: list[dict[str, Any]] = visual_config.get("edges", [])
    name_map: dict[str, str] = build_entity_name_map(nodes, edges)

    lines: list[str] = ['import { onchainTable } from "ponder";', ""]

    seen_types: set[str] = set()

    for node in nodes:
        node_type = node.get("type", "")
        if node_type not in ("entity", "aggregateentity"):
            continue

        data = node.get("data", {})
        node_id = node.get("id", "")
        resolved_name = name_map.get(node_id, data.get("name", "")).strip()
        if not resolved_name or resolved_name in seen_types:
            continue
        seen_types.add(resolved_name)

        var_name = _schema_var(resolved_name)
        lines.append(f'export const {var_name} = onchainTable("{var_name}", (t) => ({{')

        fields: list[dict[str, Any]] = data.get("fields", [])
        seen_fields: set[str] = set()

        for field in fields:
            fname = field.get("name", "").strip()
            if not fname or fname in seen_fields:
                continue
            seen_fields.add(fname)

            # Skip @derivedFrom — virtual reverse relation, not a stored column
            if field.get("derivedFrom"):
                continue

            is_id = fname == "id"
            col = _column_expr(field, is_id)
            lines.append(f"  {fname}: {col},")

        lines.append("}));")
        lines.append("")

    return "\n".join(lines)
