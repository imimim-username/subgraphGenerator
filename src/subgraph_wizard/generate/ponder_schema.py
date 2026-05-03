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
  [T!]       → t.<T>().array()  (native SQL array for mappable element types)
               t.text()          (fallback for BigDecimal or unknown element types)
  OtherEntity→ t.text()  (entity references stored as ID text; relations() generated)

@derivedFrom fields are skipped as stored columns but DO produce many()
entries in the relations() export for the owning entity.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Map from internal Graph type to Ponder column helper expression.
# The ".notNull()" suffix is applied separately when the field is required.
# Note: BigDecimal embeds a comment — handled specially in _column_expr.
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

# Primitive type names (anything not in this set is treated as an entity ref)
_KNOWN_PRIMITIVES: frozenset[str] = frozenset(_PONDER_COLUMN.keys())

# Primitives that have a clean column expression (no embedded comment),
# which makes them safe to use as array element types.
_ARRAY_SAFE: frozenset[str] = frozenset(
    k for k, v in _PONDER_COLUMN.items() if "/*" not in v
)


def _schema_var(entity_name: str) -> str:
    """Convert a PascalCase entity name to a camelCase schema variable name.

    Handles leading acronyms correctly:
        Transfer         → transfer
        TVL              → tvl
        TVLMetrics       → tvlMetrics
        ERC20Transfer    → erc20Transfer
        AlchemistDeposit → alchemistDeposit
    """
    if not entity_name:
        return "unknown"
    # Measure the leading run of uppercase characters.
    run = 0
    while run < len(entity_name) and entity_name[run].isupper():
        run += 1
    if run == 0:
        return entity_name                        # already starts lowercase
    if run == len(entity_name):
        return entity_name.lower()               # all-caps word: TVL → tvl
    if run == 1:
        return entity_name[0].lower() + entity_name[1:]   # MyEntity → myEntity
    # Multiple leading caps: last uppercase in run starts next PascalCase word
    # when followed by a lowercase char (TVLData → tvlData).
    if entity_name[run].islower():
        return entity_name[: run - 1].lower() + entity_name[run - 1 :]
    return entity_name[:run].lower() + entity_name[run:]


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

    # ── List / array types ────────────────────────────────────────────────────
    if ftype_raw.startswith("["):
        # Extract element type: "[BigInt!]" → "BigInt", "[String]" → "String"
        inner_raw = ftype_raw.strip("[]").rstrip("!")
        suffix = ".notNull()" if required else ""
        if inner_raw in _ARRAY_SAFE:
            base = _PONDER_COLUMN[inner_raw]
            return f"{base}.array(){suffix}"
        else:
            # BigDecimal arrays or unknown element types → JSON text
            return f"t.text(){suffix} /* {inner_raw} array stored as JSON text */"

    # ── Known primitive type ──────────────────────────────────────────────────
    if ftype_raw in _KNOWN_PRIMITIVES:
        col = _PONDER_COLUMN[ftype_raw]
        # BigDecimal has an embedded comment; splice .notNull() before it
        if "/* " in col:
            method_part, comment_part = col.split("/*", 1)
            method_part = method_part.rstrip()
            suffix = ".notNull()" if required else ""
            return f"{method_part}{suffix} /*{comment_part}"
        suffix = ".notNull()" if required else ""
        return f"{col}{suffix}"

    # ── Entity reference ──────────────────────────────────────────────────────
    # Store the foreign key as a text column; relations() handles the join.
    suffix = ".notNull()" if required else ""
    return f"t.text(){suffix} /* ref → {ftype_raw} */"


def render_ponder_schema(visual_config: dict[str, Any]) -> str:
    """Generate the full ponder.schema.ts content from entity nodes.

    Emits one ``onchainTable(...)`` per entity/aggregateentity node, followed
    by ``relations(...)`` exports for entity-reference fields and @derivedFrom
    reverse relations.

    Args:
        visual_config: Parsed visual-config.json dict (nodes, edges, ...).

    Returns:
        String content of ponder.schema.ts.
    """
    from subgraph_wizard.generate.graph_compiler import build_entity_name_map

    nodes: list[dict[str, Any]] = visual_config.get("nodes", [])
    edges: list[dict[str, Any]] = visual_config.get("edges", [])
    name_map: dict[str, str] = build_entity_name_map(nodes, edges)

    # ── Pass 1: build entity name → var-name map ──────────────────────────────
    # We need this before emitting tables so that relation generation can look up
    # referenced entities by name.
    entity_var_map: dict[str, str] = {}   # entity PascalCase name → camelCase var
    entity_order: list[str] = []          # resolved names in node order
    node_data_map: dict[str, dict[str, Any]] = {}  # resolved name → data dict

    seen_types: set[str] = set()
    for node in nodes:
        if node.get("type") not in ("entity", "aggregateentity"):
            continue
        data = node.get("data", {})
        node_id = node.get("id", "")
        resolved_name = name_map.get(node_id, data.get("name", "")).strip()
        if not resolved_name or resolved_name in seen_types:
            continue
        seen_types.add(resolved_name)
        var = _schema_var(resolved_name)
        entity_var_map[resolved_name] = var
        entity_order.append(resolved_name)
        node_data_map[resolved_name] = data

    # ── Pass 2: collect relations ─────────────────────────────────────────────
    # one_rels[var] = [(field_name, ref_var), ...]   — forward FK references
    # many_rels[var] = [(field_name, ref_var), ...]  — @derivedFrom reverse refs
    one_rels:  dict[str, list[tuple[str, str]]] = defaultdict(list)
    many_rels: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for resolved_name in entity_order:
        data = node_data_map[resolved_name]
        var = entity_var_map[resolved_name]
        seen_fields: set[str] = set()

        for field in data.get("fields", []):
            fname = field.get("name", "").strip()
            ftype = field.get("type", "")
            derived_from = field.get("derivedFrom")

            if not fname or fname in seen_fields:
                continue
            seen_fields.add(fname)

            # Only care about fields that reference another entity
            if ftype in _KNOWN_PRIMITIVES or ftype.startswith("[") or not ftype:
                continue
            ref_var = entity_var_map.get(ftype)
            if not ref_var:
                continue  # referenced entity not in this schema

            if derived_from:
                # @derivedFrom → many() relation (virtual, no stored column)
                many_rels[var].append((fname, ref_var))
            else:
                # Direct FK reference → one() relation
                one_rels[var].append((fname, ref_var))

    has_relations = bool(one_rels or many_rels)

    # ── Assemble import line ──────────────────────────────────────────────────
    imports = ["onchainTable"]
    if has_relations:
        imports.append("relations")
    import_line = f'import {{ {", ".join(imports)} }} from "ponder";'

    table_lines: list[str] = [import_line, ""]

    # ── Pass 3: emit onchainTable exports ─────────────────────────────────────
    for resolved_name in entity_order:
        data = node_data_map[resolved_name]
        var = entity_var_map[resolved_name]

        table_lines.append(f'export const {var} = onchainTable("{var}", (t) => ({{')

        seen_fields: set[str] = set()
        user_field_names: set[str] = set()
        for field in data.get("fields", []):
            fname = field.get("name", "").strip()
            if fname:
                user_field_names.add(fname)

        for field in data.get("fields", []):
            fname = field.get("name", "").strip()
            if not fname or fname in seen_fields:
                continue
            seen_fields.add(fname)

            # @derivedFrom fields are virtual — no stored column
            if field.get("derivedFrom"):
                continue

            is_id = fname == "id"
            col = _column_expr(field, is_id)
            table_lines.append(f"  {fname}: {col},")

            # Inject `chain` immediately after `id` (unless the user already
            # defined a field named "chain").
            if is_id and "chain" not in user_field_names:
                table_lines.append("  chain: t.text().notNull(),")
                seen_fields.add("chain")

        table_lines.append("}));")
        table_lines.append("")

    # ── Pass 4: emit relations() exports ─────────────────────────────────────
    rel_lines: list[str] = []
    all_rel_vars = sorted(set(one_rels.keys()) | set(many_rels.keys()))

    for var in all_rel_vars:
        ones = one_rels.get(var, [])
        manys = many_rels.get(var, [])

        # Build the destructuring parameter list ({ one }, { many }, { one, many })
        params: list[str] = []
        if ones:
            params.append("one")
        if manys:
            params.append("many")
        params_str = ", ".join(params)

        entries: list[str] = []
        for fname, ref_var in ones:
            entries.append(
                f"  {fname}: one({ref_var}, "
                f"{{ fields: [{var}.{fname}], references: [{ref_var}.id] }}),"
            )
        for fname, ref_var in manys:
            entries.append(f"  {fname}: many({ref_var}),")

        rel_lines.append(
            f"export const {var}Relations = relations({var}, ({{ {params_str} }}) => ({{"
        )
        rel_lines.extend(entries)
        rel_lines.append("}));")
        rel_lines.append("")

    return "\n".join(table_lines + rel_lines)
