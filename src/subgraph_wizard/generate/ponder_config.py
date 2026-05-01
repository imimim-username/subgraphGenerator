"""Generate ponder.config.ts and supporting boilerplate files.

Functions:
  render_ponder_config       — ponder.config.ts (createConfig)
  render_ponder_env_dts      — ponder-env.d.ts  (static boilerplate)
  render_ponder_api_index    — src/api/index.ts (Hono app; mounts /graphql)
  render_ponder_tsconfig     — tsconfig.json    (TypeScript config)
  render_ponder_package_json — package.json     (dependencies)
  render_ponder_env_example  — .env.example     (RPC URL hints)
  render_ponder_howto        — PONDER_HOWTO.md  (quickstart guide)

Ponder-specific design notes
-----------------------------
* GraphQL endpoint (Ponder ≥ 0.8):  The ``/graphql`` route is no longer served
  automatically.  ``render_ponder_api_index`` generates a Hono app that mounts
  ``graphql({ db, schema })`` at both ``/graphql`` (API) and ``/`` (GraphiQL
  playground).

* Auto ``chain`` column:  ``ponder_schema.py`` appends a ``chain: t.text()``
  column after ``id`` in every ``onchainTable``.  ``ponder_compiler.py`` then
  sets ``chain: context.chain.name`` on every insert so data can be filtered by
  source chain without any extra canvas wiring.

* Suffix-retry inserts:  When a Ponder insert conflicts on the primary key the
  compiler emits a retry loop that appends ``-1``, ``-2``, … until the insert
  succeeds.  This prevents duplicate-key errors from silently dropping events.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Chain IDs for common EVM networks.
# Ponder requires a numeric ``id`` per chain entry.
# Fall back to 0 if the slug is not in this table (validator warns separately).
CHAIN_IDS: dict[str, int] = {
    # ── Ethereum mainnet & testnets ───────────────────────────────────────────
    "mainnet":          1,
    "goerli":           5,           # deprecated but still used
    "sepolia":          11155111,
    "holesky":          17000,
    # ── Optimism ──────────────────────────────────────────────────────────────
    "optimism":         10,
    "optimism-goerli":  420,         # deprecated
    "optimism-sepolia": 11155420,
    # ── Base ──────────────────────────────────────────────────────────────────
    "base":             8453,
    "base-goerli":      84531,       # deprecated
    "base-sepolia":     84532,
    # ── Arbitrum ──────────────────────────────────────────────────────────────
    "arbitrum-one":     42161,
    "arbitrum-goerli":  421613,      # deprecated
    "arbitrum-sepolia": 421614,
    # ── Polygon ───────────────────────────────────────────────────────────────
    "polygon":          137,
    "mumbai":           80001,       # frontend uses "mumbai" (not "polygon-mumbai")
    "polygon-mumbai":   80001,       # alias
    "amoy":             80002,
    # ── BNB Chain ─────────────────────────────────────────────────────────────
    "bsc":              56,
    "bnb":              56,          # alias
    "bsc-testnet":      97,
    # ── Avalanche ─────────────────────────────────────────────────────────────
    "avalanche":        43114,
    "fuji":             43113,
    # ── Gnosis ────────────────────────────────────────────────────────────────
    "gnosis":           100,
    "gnosis-chiado":    10200,
    # ── zkSync ────────────────────────────────────────────────────────────────
    "zksync-era":       324,
    "zksync-sepolia":   300,
    # ── Linea ─────────────────────────────────────────────────────────────────
    "linea":            59144,
    "linea-sepolia":    59141,
    # ── Scroll ────────────────────────────────────────────────────────────────
    "scroll":           534352,
    "scroll-sepolia":   534351,
    # ── Fantom ────────────────────────────────────────────────────────────────
    "fantom":           250,
    "fantom-testnet":   4002,
    # ── Other L2s & chains ────────────────────────────────────────────────────
    "blast":            81457,
    "blast-sepolia":    168587773,
    "zora":             7777777,
    "zora-sepolia":     999999999,
    "mode":             34443,
    "mode-sepolia":     919,
    "mantle":           5000,
    "mantle-sepolia":   5003,
    "fraxtal":          252,
    "fraxtal-holesky":  2522,
    "celo":             42220,
    "celo-alfajores":   44787,
    "moonbeam":         1284,
    "moonriver":        1285,
    "aurora":           1313161554,
    "metis":            1088,
    "kava":             2222,
    "cronos":           25,
    "harmony":          1666600000,
    "taiko":            167000,
    "taiko-hekla":      167009,
    "cyber":            7560,
    "redstone":         690,
}


def _slug_to_ponder_chain_name(network_slug: str) -> str:
    """Convert a Graph network slug to a valid JS identifier for ponder chains.

    Ponder uses the chain name as a JS object key, so hyphens must become
    camelCase or underscores.  Examples:
        mainnet       → mainnet
        arbitrum-one  → arbitrumOne
        base-sepolia  → baseSepolia
    """
    parts = network_slug.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def render_ponder_config(visual_config: dict[str, Any]) -> str:
    """Generate ponder.config.ts from the visual graph config.

    Produces a ``createConfig({ database?, ordering?, chains, contracts })``
    file.  Each network in the Networks panel becomes one entry in ``chains:``.
    Each contract node maps to one entry in ``contracts:``, assigned to the
    network it is configured on.

    Emits the following options when set by the user:
    - ``database`` — postgres connection block (pglite is the default, omitted)
    - ``ordering`` — multichain (default, omitted), omnichain, experimental_isolated
    - per-chain ``pollingInterval`` and ``ethGetLogsBlockRange``
    - per-contract ``endBlock``, ``includeCallTraces``, ``includeTransactionReceipts``

    Args:
        visual_config: Parsed visual-config.json dict.

    Returns:
        String content of ponder.config.ts.
    """
    networks_config: list[dict[str, Any]] = visual_config.get("networks", [])
    nodes: list[dict[str, Any]] = visual_config.get("nodes", [])
    ponder_settings: dict[str, Any] = visual_config.get("ponder_settings", {})

    db_kind: str = ponder_settings.get("database", "pglite")
    ordering: str = ponder_settings.get("ordering", "multichain")

    # ── Collect unique network slugs in order of appearance ──────────────────
    seen_slugs: list[str] = []
    seen_set: set[str] = set()
    slug_to_entry: dict[str, dict[str, Any]] = {}
    for net_entry in networks_config:
        slug = net_entry.get("network", "").strip()
        if slug and slug not in seen_set:
            seen_slugs.append(slug)
            seen_set.add(slug)
            slug_to_entry[slug] = net_entry

    # If no network configured, use mainnet as a placeholder
    if not seen_slugs:
        seen_slugs = ["mainnet"]

    # ── Build contract node data lookup (for per-contract flags) ──────────────
    contract_node_data: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if node.get("type") == "contract":
            ct_name = node.get("data", {}).get("name", "").strip()
            if ct_name:
                contract_node_data[ct_name] = node.get("data", {})

    # ── Build contract instance list ──────────────────────────────────────────
    # Full multi-network support: collect ALL instances across all networks.
    # Each entry carries (name, chain, address, startBlock, endBlock).
    contract_entries: list[dict[str, Any]] = []
    seen_contract_types: set[str] = set()

    # First pass: pull from networks_config (has addresses + block numbers)
    for net_entry in networks_config:
        slug = net_entry.get("network", "").strip()
        if not slug:
            continue
        chain_name = _slug_to_ponder_chain_name(slug)
        contracts = net_entry.get("contracts", {})
        for ct_name, ct_data in contracts.items():
            instances = ct_data.get("instances", [])
            for inst in instances:
                addr = inst.get("address", "").strip()
                start_block = inst.get("startBlock", 0)
                try:
                    start_block = int(start_block or 0)
                except (ValueError, TypeError):
                    start_block = 0
                # Auto-detect deployment block via Etherscan when startBlock is
                # 0 and a real address is available.  Mirrors subgraph_yaml.py.
                # Requires ETHERSCAN_API_KEY in the environment; silently skips
                # if the key is absent or the lookup fails.
                _zero = "0x0000000000000000000000000000000000000000"
                if start_block == 0 and addr and addr != _zero:
                    try:
                        from subgraph_wizard.abi.etherscan import (
                            get_contract_deployment_block,
                        )
                        detected = get_contract_deployment_block(slug, addr)
                        if detected is not None:
                            start_block = detected
                    except Exception as exc:
                        logger.warning(
                            "startBlock auto-detection failed for %s on %s: %s",
                            addr, slug, exc,
                        )

                end_block_raw = inst.get("endBlock", "")
                try:
                    end_block: int | None = int(end_block_raw) if end_block_raw else None
                except (ValueError, TypeError):
                    end_block = None
                contract_entries.append({
                    "name": ct_name,
                    "chain": chain_name,
                    "address": addr,
                    "startBlock": start_block,
                    "endBlock": end_block,
                })
                seen_contract_types.add(ct_name)

    # Second pass: include contract nodes not represented in networks_config
    for node in nodes:
        if node.get("type") != "contract":
            continue
        ct_name = node.get("data", {}).get("name", "").strip()
        if not ct_name or ct_name in seen_contract_types:
            continue
        chain_name = _slug_to_ponder_chain_name(seen_slugs[0])
        contract_entries.append({
            "name": ct_name,
            "chain": chain_name,
            "address": "",
            "startBlock": 0,
            "endBlock": None,
        })
        seen_contract_types.add(ct_name)

    # ── Build ABI import list ─────────────────────────────────────────────────
    abi_imports: list[str] = []
    for ct_name in sorted(seen_contract_types):
        abi_imports.append(
            f'import {{ {ct_name}Abi }} from "./abis/{ct_name}Abi";'
        )

    # ── Render chains block ───────────────────────────────────────────────────
    chain_lines: list[str] = []
    for slug in seen_slugs:
        chain_name = _slug_to_ponder_chain_name(slug)
        chain_id = CHAIN_IDS.get(slug, 0)
        env_var = f"PONDER_RPC_URL_{chain_id}"
        net_entry = slug_to_entry.get(slug, {})

        fields: list[str] = [
            f"id: {chain_id}",
            f"rpc: process.env.{env_var}",
        ]
        polling_raw = net_entry.get("pollingInterval")
        max_range_raw = net_entry.get("ethGetLogsBlockRange")
        ws_enabled: bool = bool(net_entry.get("wsEnabled", False))
        disable_cache: bool = bool(net_entry.get("disableCache", False))

        if polling_raw not in (None, ""):
            try:
                fields.append(f"pollingInterval: {int(polling_raw)}")
            except (ValueError, TypeError):
                pass
        if max_range_raw not in (None, ""):
            try:
                fields.append(f"ethGetLogsBlockRange: {int(max_range_raw)}")
            except (ValueError, TypeError):
                pass
        if ws_enabled:
            ws_var = f"PONDER_WS_URL_{chain_id}"
            fields.append(f"ws: process.env.{ws_var}")
        if disable_cache:
            fields.append("disableCache: true")

        if len(fields) <= 2:
            # Compact single-line form when no advanced options
            chain_lines.append(
                f"    {chain_name}: {{ {', '.join(fields)} }},"
            )
        else:
            # Multi-line form when advanced options are present
            inner = "".join(f"\n      {f}," for f in fields)
            chain_lines.append(f"    {chain_name}: {{{inner}\n    }},")

    # ── Render contracts block ────────────────────────────────────────────────
    # Group by contract name, then sub-group by chain to detect multi-chain
    # deployments. Ponder uses:
    #   - string   chain: "mainnet"              when deployed on one chain
    #   - object   chain: { mainnet: {...}, ... } when deployed on multiple chains
    contracts_by_name: dict[str, list[dict[str, Any]]] = {}
    for entry in contract_entries:
        contracts_by_name.setdefault(entry["name"], []).append(entry)

    contract_lines: list[str] = []
    for ct_name in sorted(contracts_by_name.keys()):
        all_instances = contracts_by_name[ct_name]
        nd = contract_node_data.get(ct_name, {})
        include_call_traces: bool = nd.get("includeCallTraces", False)
        include_tx_receipts: bool = nd.get("includeTransactionReceipts", False)

        # Sub-group by chain (preserving original order)
        instances_by_chain: dict[str, list[dict[str, Any]]] = {}
        for inst in all_instances:
            instances_by_chain.setdefault(inst["chain"], []).append(inst)
        chains_used = list(instances_by_chain.keys())

        def _addr(inst: dict[str, Any]) -> str:
            return (
                f'"{inst["address"]}"'
                if inst["address"]
                else '"0x0000000000000000000000000000000000000000"'
            )

        if len(chains_used) == 1:
            # ── Single-chain format ──────────────────────────────────────────
            chain_name = chains_used[0]
            chain_instances = instances_by_chain[chain_name]

            # Multiple instances on the same chain → address array
            if len(chain_instances) == 1:
                addr_val = _addr(chain_instances[0])
            else:
                addr_val = "[" + ", ".join(_addr(i) for i in chain_instances) + "]"

            # Use the earliest startBlock across all instances.
            # If ANY instance has startBlock=0 (index from genesis) the effective
            # start is 0, so we omit the field entirely (Ponder's default = 0).
            all_starts = [i["startBlock"] for i in chain_instances]
            start_block = 0 if any(s == 0 for s in all_starts) else min(all_starts)

            # Use the first instance's endBlock (if consistent; omit if mixed)
            end_blocks = [i.get("endBlock") for i in chain_instances if i.get("endBlock")]
            end_block: int | None = end_blocks[0] if len(set(end_blocks)) == 1 else None

            fields = [
                f'chain: "{chain_name}"',
                f"abi: {ct_name}Abi",
                f"address: {addr_val}",
            ]
            if start_block:
                fields.append(f"startBlock: {start_block}")
            if end_block:
                fields.append(f"endBlock: {end_block}")
            if include_call_traces:
                fields.append("includeCallTraces: true")
            if include_tx_receipts:
                fields.append("includeTransactionReceipts: true")

            inner = "".join(f"\n      {f}," for f in fields)
            contract_lines.append(f"    {ct_name}: {{{inner}\n    }},")

        else:
            # ── Multi-chain format ───────────────────────────────────────────
            # Top-level fields (shared across all chains)
            top_fields: list[str] = [f"abi: {ct_name}Abi"]
            if include_call_traces:
                top_fields.append("includeCallTraces: true")
            if include_tx_receipts:
                top_fields.append("includeTransactionReceipts: true")

            # Per-chain sub-objects
            chain_obj_lines: list[str] = []
            extra_instances = 0
            for chain_name in chains_used:
                chain_instances = instances_by_chain[chain_name]
                inst = chain_instances[0]
                if len(chain_instances) > 1:
                    extra_instances += len(chain_instances) - 1

                per_chain: list[str] = [f"address: {_addr(inst)}"]
                if inst["startBlock"]:
                    per_chain.append(f"startBlock: {inst['startBlock']}")
                if inst.get("endBlock"):
                    per_chain.append(f"endBlock: {inst['endBlock']}")

                inner = "".join(f"\n          {f}," for f in per_chain)
                chain_obj_lines.append(f"        {chain_name}: {{{inner}\n        }},")

            extra_comment = ""
            if extra_instances:
                extra_comment = (
                    f"  /* {extra_instances} additional instance(s) — add manually */"
                )

            top_str = "".join(f"\n      {f}," for f in top_fields)
            chain_block = "\n".join(chain_obj_lines)
            chain_obj = f"\n      chain: {{{extra_comment}\n{chain_block}\n      }},"
            contract_lines.append(f"    {ct_name}: {{{top_str}{chain_obj}\n    }},")

    # ── Assemble file ─────────────────────────────────────────────────────────
    lines: list[str] = ['import { createConfig } from "ponder";']
    lines.extend(abi_imports)
    lines.append("")
    lines.append("export default createConfig({")

    # database block — only emit for postgres (pglite is the implicit default)
    if db_kind == "postgres":
        lines.append("  database: {")
        lines.append('    kind: "postgres",')
        lines.append("    connectionString: process.env.DATABASE_URL,")
        lines.append("  },")

    # ordering — only emit when non-default (Ponder's default is "multichain")
    if ordering and ordering != "multichain":
        lines.append(f'  ordering: "{ordering}",')

    lines.append("  chains: {")
    lines.extend(chain_lines)
    lines.append("  },")
    lines.append("  contracts: {")
    lines.extend(contract_lines)
    lines.append("  },")
    lines.append("});")
    lines.append("")

    return "\n".join(lines)


def render_ponder_env_dts() -> str:
    """Return the static ponder-env.d.ts boilerplate.

    This file is required for TypeScript to recognise the ``ponder:registry``
    and ``ponder:schema`` virtual module imports.
    """
    return '/// <reference types="ponder/env" />\n'


def render_ponder_api_index() -> str:
    """Return the content of ``src/api/index.ts``.

    Ponder requires this file to exist — even when no custom API routes are
    needed — as the entry point for the Hono-based HTTP layer.  The generated
    file exports a minimal Hono app that users can extend with custom
    endpoints (REST, tRPC, etc.).

    Returns:
        TypeScript source string.
    """
    return """\
import { db } from "ponder:api";
import schema from "ponder:schema";
import { graphql } from "ponder";
import { Hono } from "hono";

// Since Ponder 0.8 the GraphQL API is NOT served automatically — it must be
// mounted explicitly.  See: https://ponder.sh/docs/query/graphql
const app = new Hono();

app.use("/graphql", graphql({ db, schema }));

// Also serve the GraphiQL playground at / for convenience.
app.use("/", graphql({ db, schema }));

// Add custom API endpoints below.

export default app;
"""


def render_ponder_tsconfig() -> str:
    """Return a tsconfig.json matching the official Ponder project template."""
    config = {
        "compilerOptions": {
            "strict": True,
            "noUncheckedIndexedAccess": True,
            "verbatimModuleSyntax": False,
            "esModuleInterop": True,
            "isolatedModules": True,
            "allowSyntheticDefaultImports": True,
            "resolveJsonModule": True,
            "moduleResolution": "bundler",
            "module": "ESNext",
            "noEmit": True,
            "lib": ["ES2022"],
            "target": "ES2022",
            "skipLibCheck": True,
        },
        "include": ["./**/*.ts"],
        "exclude": ["node_modules"],
    }
    return json.dumps(config, indent=2) + "\n"


def render_ponder_package_json(project_name: str) -> str:
    """Return a package.json for a Ponder project.

    Args:
        project_name: The subgraph/project name (becomes the npm package name).

    Returns:
        Pretty-printed JSON string.
    """
    slug = project_name.lower().replace(" ", "-") if project_name else "my-ponder-app"
    pkg = {
        "name": slug,
        "version": "0.0.1",
        "private": True,
        "type": "module",
        "engines": {"node": ">=18.14"},
        "scripts": {
            "dev":     "ponder dev",
            "start":   "ponder start",
            "codegen": "ponder codegen",
        },
        "dependencies": {
            "hono":   "latest",
            "ponder": "latest",
            "viem":   "latest",
        },
        "devDependencies": {
            "drizzle-kit": "latest",
        },
    }
    return json.dumps(pkg, indent=2) + "\n"


def render_ponder_env_example(visual_config: dict[str, Any]) -> str:
    """Return a .env.example with RPC and optional WS URL lines per chain.

    Emits ``PONDER_RPC_URL_{chainId}`` for every chain.  When a network has
    ``wsEnabled: true``, also emits a ``PONDER_WS_URL_{chainId}`` line.

    Args:
        visual_config: Parsed visual-config.json dict.

    Returns:
        Content of .env.example.
    """
    networks_config: list[dict[str, Any]] = visual_config.get("networks", [])

    seen_slugs: list[str] = []
    seen_set: set[str] = set()
    slug_to_entry: dict[str, dict[str, Any]] = {}
    for net_entry in networks_config:
        slug = net_entry.get("network", "").strip()
        if slug and slug not in seen_set:
            seen_slugs.append(slug)
            seen_set.add(slug)
            slug_to_entry[slug] = net_entry

    if not seen_slugs:
        seen_slugs = ["mainnet"]

    lines: list[str] = [
        "# Ponder RPC URLs — one per chain.",
        "# Replace the placeholder with your Alchemy / Infura / etc. endpoint.",
        "",
    ]
    for slug in seen_slugs:
        chain_id = CHAIN_IDS.get(slug, 0)
        lines.append(f"PONDER_RPC_URL_{chain_id}=https://eth-{slug}.g.alchemy.com/v2/YOUR_KEY")
        if slug_to_entry.get(slug, {}).get("wsEnabled"):
            lines.append(
                f"PONDER_WS_URL_{chain_id}=wss://eth-{slug}.g.alchemy.com/v2/YOUR_KEY"
            )

    lines += [
        "",
        "# ── Database (production / ponder start) ────────────────────────────────",
        "#",
        "# ponder dev  → uses embedded PGlite; no database vars needed.",
        "# ponder start → requires a real PostgreSQL database AND a schema name.",
        "#",
        "# Uncomment and fill in both lines to use PostgreSQL:",
        "# DATABASE_URL=postgresql://ponder:yourpassword@localhost:5432/ponder",
        "# DATABASE_SCHEMA=public",
        "#",
        "# DATABASE_SCHEMA must be unique per running Ponder instance.",
        "# Two instances cannot share the same schema at the same time.",
        "",
    ]
    return "\n".join(lines)


def render_ponder_howto(
    project_name: str,
    output_dir: str,
    visual_config: dict[str, Any] | None = None,
) -> str:
    """Return a PONDER_HOWTO.md quickstart guide tailored to the canvas settings.

    Args:
        project_name: The subgraph/project name.
        output_dir: The path to the generated project directory.
        visual_config: Parsed visual-config.json dict used to tailor the guide.

    Returns:
        Markdown string.
    """
    visual_config = visual_config or {}
    ponder_settings: dict[str, Any] = visual_config.get("ponder_settings", {})
    networks_config: list[dict[str, Any]] = visual_config.get("networks", [])
    nodes: list[dict[str, Any]] = visual_config.get("nodes", [])

    db_kind: str = ponder_settings.get("database", "pglite")
    ordering: str = ponder_settings.get("ordering", "multichain")
    use_postgres = db_kind == "postgres"

    # Collect unique chain slugs → env var names
    seen_slugs: list[str] = []
    seen_set: set[str] = set()
    for net in networks_config:
        slug = net.get("network", "").strip()
        if slug and slug not in seen_set:
            seen_slugs.append(slug)
            seen_set.add(slug)
    if not seen_slugs:
        seen_slugs = ["mainnet"]
    rpc_vars = [f"PONDER_RPC_URL_{CHAIN_IDS.get(s, 0)}" for s in seen_slugs]

    # Detect setup handlers
    has_setup = any(
        n.get("type") == "contract" and n.get("data", {}).get("hasSetupHandler")
        for n in nodes
    )

    # Collect entity / aggregate entity names for GraphQL examples
    entity_names: list[str] = []
    for n in nodes:
        if n.get("type") in ("entity", "aggregateentity"):
            nm = n.get("data", {}).get("name", "").strip()
            if nm:
                entity_names.append(nm)
    example_table = (
        entity_names[0][0].lower() + entity_names[0][1:] + "s"
        if entity_names else "myTable"
    )
    # Build a list of example field names from the first entity node
    example_fields: list[str] = ["id", "chain"]
    for n in nodes:
        if n.get("type") in ("entity", "aggregateentity") and entity_names:
            nm = n.get("data", {}).get("name", "").strip()
            if nm == entity_names[0]:
                for f in (n.get("data", {}).get("fields") or [])[:3]:
                    fname = f.get("name", "").strip()
                    if fname and fname not in example_fields:
                        example_fields.append(fname)
                break

    # ── RPC URL step (shared) ────────────────────────────────────────────────
    rpc_env_lines = "\n".join(
        f"{v}=https://eth-{s}.g.alchemy.com/v2/YOUR_KEY"
        for v, s in zip(rpc_vars, seen_slugs)
    )
    chains_list = ", ".join(f"**{s}**" for s in seen_slugs)
    step_rpc = f"""\
## Step 2 — Get an RPC endpoint

To read blockchain data, Ponder needs to connect to a blockchain node via an
**RPC (Remote Procedure Call) endpoint** — a URL that lets your indexer send
requests like "give me all events from block 18000000 to 18001000".

This project indexes: {chains_list}.
You need one RPC URL per chain.

### Get a free endpoint from Alchemy

[Alchemy](https://alchemy.com) provides free RPC endpoints and is the easiest
option for getting started.

1. Go to <https://alchemy.com> and sign up for a free account.
2. Click **"Create new app"**.
3. Give it a name (anything, e.g. *my-ponder-app*).
4. Select the network(s) you need (match the chain(s) listed above).
5. Click **"Create app"**.
6. On the app dashboard, click **"API key"** (top right).
7. Copy the **HTTPS** URL — it looks like:
   `https://eth-mainnet.g.alchemy.com/v2/abc123XYZ...`

Repeat for each chain if you need more than one.

> **Alternatives:** [Infura](https://infura.io), [QuickNode](https://quicknode.com),
> [Ankr](https://ankr.com), and [drpc.org](https://drpc.org) all offer free tiers.
> Any HTTPS RPC endpoint works — just paste the URL in the next step.

You'll paste these URLs into `.env.local` in Step 3."""

    # ── Step 3: database + env file ──────────────────────────────────────────
    if use_postgres:
        step_db = f"""\
## Step 3 — Set up PostgreSQL and configure environment variables

This project uses PostgreSQL as its database.  You need a running Postgres
server before starting the indexer.

### 3a — Install PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Ubuntu / Debian (including WSL on Windows):**
```bash
sudo apt update && sudo apt install -y postgresql
sudo systemctl start postgresql
sudo systemctl enable postgresql   # auto-start on reboot
```

**Managed cloud (no local install — easiest option):**
- [Supabase](https://supabase.com) — free tier, includes a connection string
- [Neon](https://neon.tech) — free tier, serverless Postgres
- [Railway](https://railway.app) — free tier, one-click Postgres

If you use a managed service, skip to step 3c and use the connection string
they provide.

### 3b — Create the database and user

> **Linux note — "Peer authentication failed":**
> On Linux, PostgreSQL only lets you log in as the `postgres` superuser if you
> are *also* running as the `postgres` Linux system user.  Typing
> `psql -U postgres` in a normal terminal will fail.  Use `sudo -u postgres psql`
> instead — this switches to the postgres system user first.

```bash
sudo -u postgres psql
```

> **macOS (Homebrew) note:** Try `psql postgres` (no sudo) — Homebrew makes
> your own macOS username the superuser.

You should see a prompt like `postgres=#`.  Now type these commands exactly,
pressing Enter after each one.  Replace `yourpassword` with a password you
choose (write it down — you'll need it again):

```sql
CREATE DATABASE ponder;
CREATE USER ponder WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE ponder TO ponder;
\\c ponder
GRANT ALL ON SCHEMA public TO ponder;
\\q
```

**What each line does:**
- `CREATE DATABASE ponder` — creates a new empty database called `ponder`
- `CREATE USER ponder WITH PASSWORD ...` — creates a login for Ponder to use
- `GRANT ALL PRIVILEGES ON DATABASE ponder TO ponder` — lets that user access the database
- `\\c ponder` — switches psql into the `ponder` database
- `GRANT ALL ON SCHEMA public TO ponder` — lets the user create tables (required on PostgreSQL 15+)
- `\\q` — exits psql

### 3c — Verify the connection

Before going further, confirm Ponder can actually reach the database:

```bash
psql "postgresql://ponder:yourpassword@localhost:5432/ponder"
```

Replace `yourpassword` with the password you chose above.
You should see a `ponder=>` prompt.  Type `\\q` to exit.

If you get an error, see the Troubleshooting section at the bottom of this file.

Do not proceed until this command works.

### 3d — Create `.env.local`

```bash
cd "{output_dir}"
cp .env.example .env.local
```

Open `.env.local` in any text editor and fill in every blank value:

```
# ── RPC endpoints ─────────────────────────────────────────────────────────
# Paste your Alchemy (or other provider) HTTPS URLs here.
{rpc_env_lines}

# ── Database ───────────────────────────────────────────────────────────────
# The connection string for your PostgreSQL database.
DATABASE_URL=postgresql://ponder:yourpassword@localhost:5432/ponder

# The schema (namespace) Ponder will use inside the database.
# 'public' is fine for a single instance.  Use a different name
# if you run multiple Ponder instances against the same database.
DATABASE_SCHEMA=public
```

> **Important:** Ponder reads `.env.local`, not `.env`.
> Make sure the file is named exactly `.env.local`."""
    else:
        step_db = f"""\
## Step 3 — Configure environment variables

### 3a — Create `.env.local`

```bash
cd "{output_dir}"
cp .env.example .env.local
```

Open `.env.local` in any text editor and fill in your RPC URL(s):

```
# Paste your Alchemy (or other provider) HTTPS URLs here.
{rpc_env_lines}
```

> **Important:** Ponder reads `.env.local`, not `.env`.
> Make sure the file is named exactly `.env.local`.

### 3b — About the database

This project uses **PGlite** — a lightweight Postgres database that runs
entirely inside Node.js.  You do **not** need to install PostgreSQL or set up
any database server.  Ponder handles everything automatically and stores data
in a local `.ponder/pglite/` folder.

> **For production (`pnpm start`)**, PGlite is not supported.
> You will need to switch to PostgreSQL when deploying.  See
> Step 7 — Production deployment."""

    # ── Ordering note ────────────────────────────────────────────────────────
    ordering_note = ""
    if ordering == "omnichain":
        ordering_note = """\

> **Ordering note:** This project uses `omnichain` ordering, which guarantees
> deterministic global event ordering across all chains by block timestamp.
> Indexing is slower than the default `multichain` mode but ensures strict
> cross-chain consistency."""
    elif ordering == "experimental_isolated":
        ordering_note = """\

> **Ordering note:** This project uses `experimental_isolated` ordering.
> Each chain gets its own isolated database schema.  You **must** include
> `chainId` in every table's primary key.  See the Ponder docs for details."""

    # ── Setup handler note ───────────────────────────────────────────────────
    setup_note = ""
    if has_setup:
        setup_note = """\

> **Setup handlers:** One or more contracts have a `:setup` handler that runs
> once before indexing begins (at `startBlock`).  This is used to seed initial
> state.  The handler has access to `context.db` but **not** `event` — any
> generated code using `event.*` inside setup will need manual adjustment."""

    # ── GraphQL field list for examples ─────────────────────────────────────
    fields_str = "\n      ".join(example_fields)

    # ── Production section — tailored to database ────────────────────────────
    step_num_prod = 7
    if use_postgres:
        prod_section = f"""\
## Step {step_num_prod} — Production deployment

Your project is already configured for PostgreSQL, so production is
straightforward.  You just need a server that can run Node.js and reach
your database.

### Environment variables

Make sure these are set on your production server (or in your hosting
platform's secrets / environment variables dashboard):

```
DATABASE_URL=postgresql://ponder:yourpassword@host:5432/ponder
DATABASE_SCHEMA=public
{rpc_env_lines}
```

> **Managed Postgres (Supabase, Neon, Railway):** Use the connection string
> they give you.  If connections fail, try adding `?sslmode=require` to the URL.

> **PostgreSQL 15+ schema permissions:** If Ponder fails with
> `permission denied for schema public`, run this once on the database:
> ```sql
> GRANT ALL ON SCHEMA public TO ponder;
> ```
> On managed databases, look for a "Schema privileges" option in the dashboard.

### Start

```bash
pnpm start
```

**Popular hosting options:**
- [Railway](https://railway.app) — add a Postgres service and a Node.js service, set env vars in the dashboard
- [Render](https://render.com) — Web Service + Render Postgres (free tier available)
- [Fly.io](https://fly.io) — `fly launch` then `fly postgres create`

> **Schema conflicts:** If you run two Ponder instances against the same database,
> give each a different `DATABASE_SCHEMA` (e.g. `staging`, `prod`).
> Two instances cannot share the same schema at the same time."""
    else:
        prod_section = f"""\
## Step {step_num_prod} — Production deployment

PGlite works great for development but **does not support `pnpm start`**.
Before deploying to production you must switch to a real PostgreSQL database.

### 7a — Create a PostgreSQL database

Follow the PostgreSQL setup instructions from Step 3 of the postgres version
of this guide, or use a managed service (easiest):

- [Supabase](https://supabase.com) — free tier, gives you a connection string
- [Neon](https://neon.tech) — free tier, serverless Postgres
- [Railway](https://railway.app) — add a Postgres service, get a connection string

### 7b — Add Postgres to `ponder.config.ts`

Open `ponder.config.ts` and add a `database` block:

```typescript
export default createConfig({{
  database: {{
    kind: "postgres",
    connectionString: process.env.DATABASE_URL,
  }},
  // ... rest of the config stays the same
}});
```

### 7c — Set environment variables

Add these to `.env.local` (local) or your hosting platform's secrets dashboard
(production):

```
DATABASE_URL=postgresql://ponder:yourpassword@host:5432/ponder
DATABASE_SCHEMA=public
{rpc_env_lines}
```

> If your Postgres provider requires SSL, add `?sslmode=require` to the URL.

`DATABASE_SCHEMA` names the namespace inside the database where Ponder creates
its tables.  `public` is fine for a single instance.

### 7d — Start

```bash
pnpm start
```"""

    return f"""\
# How to Run "{project_name}" with Ponder

**What this is:** Ponder is a blockchain indexer.  It connects to the Ethereum
network (or other EVM chains), reads every event emitted by the smart contracts
you configured, runs your handler code for each event, and stores the results in
a database.  Once it's running, you can query all that data instantly through a
GraphQL API — no waiting for RPC calls, no parsing raw transaction logs yourself.

**What you'll end up with:**
- A running indexer that stays up to date with the chain in real time
- A GraphQL API at `http://localhost:42069/graphql`
- An interactive query playground in your browser where you can explore the data
{ordering_note}{setup_note}

---

## Step 1 — Install Node.js and pnpm

Ponder requires **Node.js 18 or later**.  The easiest way to install it is via
`nvm` (Node Version Manager), which lets you switch Node versions without
touching your system install.

```bash
# 1. Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# 2. Close and reopen your terminal, then install Node 20
nvm install 20
nvm use 20

# 3. Install pnpm (the package manager Ponder uses)
npm install -g pnpm

# 4. Verify everything installed correctly
node --version    # should print v20.x.x
pnpm --version    # should print 8.x.x or later
```

If `nvm` is not found after reopening the terminal, run:
```bash
source ~/.bashrc    # Linux / WSL
source ~/.zshrc     # macOS with zsh
```

---

{step_rpc}

---

{step_db}

---

## Step 4 — Install project dependencies

This downloads Ponder and all the other packages this project needs.

```bash
cd "{output_dir}"
pnpm install
```

This may take a minute.  When it finishes you should see something like
`Done in Xs`.

> **"Ignored build scripts: esbuild"** — if you see this warning, run:
> ```bash
> pnpm approve-builds
> ```
> Select all `esbuild` entries and approve them.  Ponder may not start
> correctly without this step.

---

## Step 5 — Start the indexer

```bash
pnpm dev
```

> **`pnpm dev` vs `pnpm start`:**
> - `pnpm dev` — for local development.  Supports hot-reload (automatically
>   restarts when you edit handler code).  Uses PGlite if no database config
>   is set, otherwise uses your `DATABASE_URL`.
> - `pnpm start` — for production servers only.  Always requires PostgreSQL
>   and `DATABASE_SCHEMA`.  Do not use this for local development.

### What you'll see in the terminal

A healthy startup looks like this:

```
INFO  Connected to database type=postgres ...
INFO  Connected to JSON-RPC chain=mainnet ...
INFO  Started syncing ...  startBlock=18000000
```

Then it will show a progress bar as it works through historical blocks:

```
INFO  Syncing ... 12% (block 18120000 / 19000000)
INFO  Syncing ... 34% (block 18620000 / 19000000)
```

**This can take a long time** (minutes to hours) depending on how many blocks
it needs to process.  The further back your `startBlock` is, the longer it takes.
Leave the terminal open and let it run.

Once it catches up to the current block it will print:

```
INFO  Realtime sync started
```

At that point your data is live and the GraphQL API is ready to query.

### How to stop the indexer

Press **Ctrl + C** in the terminal.  Your data is saved in the database and
will still be there when you restart.  The next time you run `pnpm dev` or
`pnpm start`, Ponder will pick up from where it left off.

---

## Step 6 — View and query your data

Once the indexer is running (even before it finishes syncing historical data),
open your browser and go to:

**<http://localhost:42069/graphql>**

You will see the **GraphiQL playground** — an interactive query editor built
into Ponder.  It looks like a split-screen text editor.

### What is GraphQL?

GraphQL is a query language for APIs.  Instead of fixed endpoints like REST
(`/api/transfers`, `/api/users`), you write a query that describes exactly which
fields you want, and the API returns just those fields.

### Your first query

Click in the left panel of the playground and type:

```graphql
{{
  {example_table}(limit: 10) {{
    items {{
      {fields_str}
    }}
  }}
}}
```

Then press the **▶ Run** button (or Ctrl+Enter).  The right panel will show
the results as JSON.

### Discover all available tables and fields

Click the **"Schema"** tab on the right side of the playground (or the book
icon).  This shows every table and every field available to query — it's
generated automatically from the entities you defined on the canvas.

You can also click **"Docs"** to browse the full auto-generated API documentation.

### Useful query patterns

**Get the most recent 20 records:**
```graphql
{{
  {example_table}(limit: 20, orderBy: "id", orderDirection: "desc") {{
    items {{
      {fields_str}
    }}
  }}
}}
```

**Filter by chain (if you index multiple networks):**
```graphql
{{
  {example_table}(where: {{ chain: "mainnet" }}, limit: 10) {{
    items {{
      {fields_str}
    }}
  }}
}}
```

**Get the total count:**
```graphql
{{
  {example_table}(limit: 1) {{
    totalCount
  }}
}}
```

> **Auto `chain` field:** Every table has a `chain` column automatically added
> by the generator (`chain: context.chain.name` on every insert).  Use it to
> separate data from different networks in your queries.

### Query via curl (command line)

If you prefer the command line over the browser playground:

```bash
curl -X POST http://localhost:42069/graphql \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "{{ {example_table}(limit: 5) {{ items {{ {" ".join(example_fields)} }} }} }}"}}'
```

---

{prod_section}

---

## Quick reference

| Command        | Description                                      |
|----------------|--------------------------------------------------|
| `pnpm dev`     | Start indexer with hot-reload (development)      |
| `pnpm start`   | Start indexer in production mode                 |
| `pnpm codegen` | Regenerate TypeScript types after schema changes |
| Ctrl + C       | Stop the indexer                                 |

| URL | What it is |
|---|---|
| `http://localhost:42069/graphql` | GraphiQL playground + GraphQL API |

---

## Troubleshooting

**Indexing is slow / taking a long time**
→ This is normal.  The time depends on how many blocks Ponder needs to process.
  If `startBlock` is set to a very early block number, it may take hours.
  To speed up: open `ponder.config.ts`, find your contract's `startBlock`,
  and set it to a more recent block (closer to the current block number).
  You can look up a contract's deployment block on Etherscan.

**GraphQL returns empty results**
→ The indexer may still be syncing.  Check the terminal — if it still shows
  a progress percentage, wait until it reaches 100% (or at least until it
  has passed the blocks where your events occurred).  Alternatively, query
  `totalCount` to see if any records exist yet.

**GraphQL playground shows "Network error"**
→ The indexer is not running.  Start it with `pnpm dev` and wait for the
  `Realtime sync started` line before opening the playground.

**`Error: Invalid RPC URL`**
→ Check that your `PONDER_RPC_URL_*` variable(s) are set in `.env.local` and
  are valid HTTPS URLs.  Required variable(s) for this project:
  {", ".join(f"`{v}`" for v in rpc_vars)}

**`Peer authentication failed for user "postgres"`** (when running `psql -U postgres`)
→ On Linux, PostgreSQL only allows you to log in as the `postgres` database user
  if you are also the `postgres` Linux system user.  Use `sudo` instead:
  ```bash
  sudo -u postgres psql
  ```

**`BuildError: Database schema required`** (when running `pnpm start`)
→ `DATABASE_SCHEMA` is missing from `.env.local`.  Add it:
  ```
  DATABASE_SCHEMA=public
  ```
  Note: only `pnpm start` requires this — `pnpm dev` does not.

**`Error: DATABASE_URL is not set`**{' (only relevant if you switch to postgres)' if not use_postgres else ''}
→ Add `DATABASE_URL` to `.env.local`.  See Step 3 for the correct format.

**`Connection terminated unexpectedly`** (repeats 5 times then exits)
→ Ponder connected to PostgreSQL but was immediately rejected.  Work through
  this checklist:

  1. Is PostgreSQL running?
     ```bash
     sudo systemctl status postgresql
     sudo systemctl start postgresql   # if inactive
     ```
  2. Check the PostgreSQL log for the real error:
     ```bash
     sudo journalctl -u postgresql -n 30
     ```
  3. Test the credentials directly:
     ```bash
     psql "postgresql://ponder:yourpassword@localhost:5432/ponder"
     ```
     - `password authentication failed` → wrong password; reset with:
       `sudo -u postgres psql -c "ALTER USER ponder WITH PASSWORD 'new';"`
     - `database does not exist` → re-run Step 3b
     - `connection refused` → PostgreSQL is not running (see step 1 above)
  4. Make sure `.env.local` exists and has the correct `DATABASE_URL`:
     ```bash
     cat .env.local
     ```

**`permission denied for schema public`**
→ PostgreSQL 15+ revoked the default schema `CREATE` privilege.  Run:
  ```bash
  sudo -u postgres psql -d ponder -c "GRANT ALL ON SCHEMA public TO ponder;"
  ```

**`SyntaxError` in generated handler code**
→ Regenerate from the canvas.  Some complex type combinations may need
  manual adjustment in `src/index.ts`.

**BigDecimal fields show as text**
→ Ponder has no native arbitrary-precision decimal type.  BigDecimal fields
   are stored as text strings.  To do arithmetic, parse with a library such
   as `decimal.js`, or store values in base units (e.g. wei as BigInt).
"""
