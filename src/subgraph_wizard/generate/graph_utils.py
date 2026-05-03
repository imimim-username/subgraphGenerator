"""Shared data structures and utilities used by both the AssemblyScript and
Ponder compilers.

Placing ``Edge`` and ``build_entity_name_map`` here removes the coupling
between ``ponder_compiler`` and ``graph_compiler`` — neither Ponder-specific
nor Graph-specific code belongs in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Edge:
    """Directed edge between two nodes in the visual graph."""

    id: str
    source: str          # node id
    source_handle: str   # output port id
    target: str          # node id
    target_handle: str   # input port id


def schema_var(entity_name: str) -> str:
    """Convert a PascalCase entity name to a camelCase Ponder schema variable name.

    Used by both ``ponder_compiler`` and ``ponder_schema`` to produce the
    camelCase identifier that Ponder exports from ``ponder:schema``.

    Handles leading acronyms correctly:
        Transfer         → transfer
        TVL              → tvl
        TVLMetrics       → tvlMetrics
        ERC20Transfer    → erc20Transfer
        AlchemistDeposit → alchemistDeposit
        alreadyLower     → alreadyLower
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
    # Multiple leading caps: the last uppercase letter in the run is the start
    # of the next PascalCase word when followed by a lowercase char
    # (TVLData: run "TVLD", next 'a' → keep 'D' → tvlData).
    # When followed by a digit or other non-lower char, lowercase the whole run.
    if entity_name[run].islower():
        return entity_name[: run - 1].lower() + entity_name[run - 1 :]
    return entity_name[:run].lower() + entity_name[run:]


def build_entity_name_map(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, str]:
    """Return ``{entity_node_id: graphql_type_name}``.

    Entity names are kept as-is when they are unique across the canvas.
    When multiple entity nodes share the same name (e.g. two contracts both
    have a ``Deposit`` event entity), each is prefixed with the name of the
    contract node that feeds into it:

        alchemistV3  + Deposit  →  AlchemistV3Deposit
        transmuterV3 + Deposit  →  TransmuterV3Deposit

    The prefix is derived by BFS backwards through edges from the entity node
    to the first contract node found upstream.  If no contract is found the raw
    name is used with a short node-ID suffix to guarantee uniqueness.
    """
    entity_nodes: dict[str, str] = {
        n["id"]: n["data"].get("name", "")
        for n in nodes
        if n.get("type") in ("entity", "aggregateentity") and n.get("data", {}).get("name")
    }
    contract_nodes: dict[str, str] = {
        n["id"]: n["data"].get("name", "")
        for n in nodes
        if n.get("type") == "contract" and n.get("data", {}).get("name")
    }

    # Count how many times each base name appears
    name_counts: dict[str, int] = {}
    for name in entity_nodes.values():
        name_counts[name] = name_counts.get(name, 0) + 1

    # Build backwards adjacency: target_id → [source_id, …]
    incoming: dict[str, list[str]] = {}
    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if src and tgt:
            incoming.setdefault(tgt, []).append(src)

    def _find_contract(entity_id: str) -> str:
        """BFS backwards from entity node to the first contract node."""
        queue = [entity_id]
        visited: set[str] = {entity_id}
        while queue:
            cur = queue.pop(0)
            for src in incoming.get(cur, []):
                if src in visited:
                    continue
                visited.add(src)
                if src in contract_nodes:
                    return contract_nodes[src]
                queue.append(src)
        return ""

    result: dict[str, str] = {}
    for node_id, name in entity_nodes.items():
        if name_counts[name] > 1:
            contract_name = _find_contract(node_id)
            if contract_name:
                prefix = contract_name[0].upper() + contract_name[1:]
                result[node_id] = f"{prefix}{name}"
            else:
                result[node_id] = f"{name}_{node_id[:6]}"
        else:
            result[node_id] = name

    return result
