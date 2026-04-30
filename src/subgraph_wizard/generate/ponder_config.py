"""Generate ponder.config.ts and supporting boilerplate files.

Functions:
  render_ponder_config    — ponder.config.ts (createConfig)
  render_ponder_env_dts   — ponder-env.d.ts  (static boilerplate)
  render_ponder_tsconfig  — tsconfig.json    (TypeScript config)
  render_ponder_package_json — package.json  (dependencies)
  render_ponder_env_example  — .env.example  (RPC URL hints)
  render_ponder_howto     — PONDER_HOWTO.md  (quickstart guide)
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
    "mainnet":          1,
    "sepolia":          11155111,
    "holesky":          17000,
    "polygon":          137,
    "polygon-mumbai":   80001,
    "amoy":             80002,
    "arbitrum-one":     42161,
    "arbitrum-sepolia": 421614,
    "optimism":         10,
    "optimism-sepolia": 11155420,
    "base":             8453,
    "base-sepolia":     84532,
    "avalanche":        43114,
    "bsc":              56,
    "bsc-testnet":      97,
    "gnosis":           100,
    "gnosis-chiado":    10200,
    "fantom":           250,
    "zksync-era":       324,
    "zksync-sepolia":   300,
    "linea":            59144,
    "linea-sepolia":    59141,
    "scroll":           534352,
    "scroll-sepolia":   534351,
    "celo":             42220,
    "moonbeam":         1284,
    "moonriver":        1285,
    "aurora":           1313161554,
    "bnb":              56,          # alias
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

    Produces a ``createConfig({ chains, contracts })`` file.  Each network in
    the Networks panel becomes one entry in ``chains:``.  Each contract node
    maps to one entry in ``contracts:``, assigned to the network it is
    configured on.

    Args:
        visual_config: Parsed visual-config.json dict.

    Returns:
        String content of ponder.config.ts.
    """
    networks_config: list[dict[str, Any]] = visual_config.get("networks", [])
    nodes: list[dict[str, Any]] = visual_config.get("nodes", [])

    # ── Collect unique network slugs in order of appearance ──────────────────
    seen_slugs: list[str] = []
    seen_set: set[str] = set()
    for net_entry in networks_config:
        slug = net_entry.get("network", "").strip()
        if slug and slug not in seen_set:
            seen_slugs.append(slug)
            seen_set.add(slug)

    # If no network configured, use mainnet as a placeholder
    if not seen_slugs:
        seen_slugs = ["mainnet"]

    # ── Map: contract_type_name → (network_slug, address, startBlock) ────────
    # When a contract type has multiple instances (multi-network), we pick one
    # chain per contract (first configured network for that contract type).
    # Full multi-network support: emit ALL instances across all networks.
    # We'll build a list of (contract_type, chain_name, address, startBlock).
    contract_entries: list[dict[str, Any]] = []
    seen_contract_types: set[str] = set()

    # First pass: pull from networks_config (has addresses + startBlocks)
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
                contract_entries.append({
                    "name": ct_name,
                    "chain": chain_name,
                    "address": addr,
                    "startBlock": start_block,
                })
                seen_contract_types.add(ct_name)

    # Second pass: include contract nodes not represented in networks_config
    for node in nodes:
        if node.get("type") != "contract":
            continue
        ct_name = node.get("data", {}).get("name", "").strip()
        if not ct_name or ct_name in seen_contract_types:
            continue
        # Use first seen network slug as fallback
        chain_name = _slug_to_ponder_chain_name(seen_slugs[0])
        contract_entries.append({
            "name": ct_name,
            "chain": chain_name,
            "address": "",
            "startBlock": 0,
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
        chain_lines.append(
            f"    {chain_name}: {{ id: {chain_id}, rpc: process.env.{env_var} }},"
        )

    # ── Render contracts block ────────────────────────────────────────────────
    # Group by contract name; when multiple instances exist on different chains,
    # Ponder supports per-chain config via an array of addresses.
    # For simplicity, we emit one entry per (contract, chain) combination.
    # Users can merge them manually for factory/multi-address patterns.
    contracts_by_name: dict[str, list[dict]] = {}
    for entry in contract_entries:
        contracts_by_name.setdefault(entry["name"], []).append(entry)

    contract_lines: list[str] = []
    for ct_name in sorted(contracts_by_name.keys()):
        instances = contracts_by_name[ct_name]
        if len(instances) == 1:
            inst = instances[0]
            addr_val = f'"{inst["address"]}"' if inst["address"] else '"0x0000000000000000000000000000000000000000"'
            sb_line = f"\n      startBlock: {inst['startBlock']}," if inst["startBlock"] else ""
            contract_lines.append(
                f"    {ct_name}: {{\n"
                f"      chain: \"{inst['chain']}\",\n"
                f"      abi: {ct_name}Abi,\n"
                f"      address: {addr_val},{sb_line}\n"
                f"    }},"
            )
        else:
            # Multiple instances — emit as first instance and comment about extras
            inst = instances[0]
            addr_val = f'"{inst["address"]}"' if inst["address"] else '"0x0000000000000000000000000000000000000000"'
            sb_line = f"\n      startBlock: {inst['startBlock']}," if inst["startBlock"] else ""
            extras = instances[1:]
            comment = f"  /* {len(extras)} additional instance(s) not shown — add manually */"
            contract_lines.append(
                f"    {ct_name}: {{{comment}\n"
                f"      chain: \"{inst['chain']}\",\n"
                f"      abi: {ct_name}Abi,\n"
                f"      address: {addr_val},{sb_line}\n"
                f"    }},"
            )

    # ── Assemble file ─────────────────────────────────────────────────────────
    lines: list[str] = ['import { createConfig } from "ponder";']
    lines.extend(abi_imports)
    lines.append("")
    lines.append("export default createConfig({")
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


def render_ponder_tsconfig() -> str:
    """Return a tsconfig.json suitable for a Ponder project."""
    config = {
        "compilerOptions": {
            "target": "ES2022",
            "module": "ES2022",
            "moduleResolution": "bundler",
            "strict": True,
            "paths": {
                "ponder:registry": ["./ponder-env.d.ts"],
                "ponder:schema": ["./ponder-env.d.ts"],
            },
        },
        "include": ["src/**/*.ts", "ponder.config.ts", "ponder.schema.ts"],
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
        "scripts": {
            "dev":   "ponder dev",
            "start": "ponder start",
            "codegen": "ponder codegen",
        },
        "dependencies": {
            "hono":       "latest",
            "ponder":     "latest",
            "viem":       "latest",
        },
        "devDependencies": {
            "drizzle-kit": "latest",
        },
    }
    return json.dumps(pkg, indent=2) + "\n"


def render_ponder_env_example(visual_config: dict[str, Any]) -> str:
    """Return a .env.example with one PONDER_RPC_URL_{chainId}= line per chain.

    Args:
        visual_config: Parsed visual-config.json dict.

    Returns:
        Content of .env.example.
    """
    networks_config: list[dict[str, Any]] = visual_config.get("networks", [])

    seen_slugs: list[str] = []
    seen_set: set[str] = set()
    for net_entry in networks_config:
        slug = net_entry.get("network", "").strip()
        if slug and slug not in seen_set:
            seen_slugs.append(slug)
            seen_set.add(slug)

    if not seen_slugs:
        seen_slugs = ["mainnet"]

    lines: list[str] = [
        "# Ponder RPC URLs — one per chain.",
        "# Replace the placeholder with your Alchemy / Infura / etc. endpoint.",
        "",
    ]
    for slug in seen_slugs:
        chain_id = CHAIN_IDS.get(slug, 0)
        env_var = f"PONDER_RPC_URL_{chain_id}"
        lines.append(f"{env_var}=https://eth-{slug}.g.alchemy.com/v2/YOUR_KEY")

    lines += [
        "",
        "# Uncomment to use a PostgreSQL database instead of the embedded PGlite.",
        "# DATABASE_URL=postgresql://user:password@localhost:5432/ponder",
        "",
    ]
    return "\n".join(lines)


def render_ponder_howto(project_name: str, output_dir: str) -> str:
    """Return a PONDER_HOWTO.md quickstart guide.

    Args:
        project_name: The subgraph/project name.
        output_dir: The path to the generated project directory.

    Returns:
        Markdown string.
    """
    slug = project_name.lower().replace(" ", "-") if project_name else "my-ponder-app"
    return f"""\
# How to Run "{project_name}" with Ponder

This guide walks you through installing and running your generated Ponder
indexer from a clean machine.

---

## Step 1 — Install Node.js & pnpm

Ponder requires **Node.js 18 or later** and **pnpm**.

```bash
# Install Node via nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 20 && nvm use 20

# Install pnpm
npm install -g pnpm

# Verify
node --version   # v20.x.x
pnpm --version   # 8.x.x or later
```

---

## Step 2 — Configure your RPC URL

Copy `.env.example` to `.env` and fill in your RPC endpoint:

```bash
cd "{output_dir}"
cp .env.example .env
# Edit .env and replace "YOUR_KEY" with your Alchemy / Infura key
```

Ponder reads `PONDER_RPC_URL_{{chainId}}` from the environment.  For example,
`PONDER_RPC_URL_1` is the mainnet RPC and `PONDER_RPC_URL_42161` is Arbitrum One.

---

## Step 3 — Install dependencies

```bash
cd "{output_dir}"
pnpm install
```

---

## Step 4 — Run the indexer (development mode)

```bash
pnpm dev
```

Ponder will:
1. Sync historical events from the configured `startBlock` to the chain tip.
2. Start a GraphQL API at <http://localhost:42069/graphql>.
3. Hot-reload handlers when you edit `src/index.ts`.

---

## Step 5 — Query the data

Open <http://localhost:42069/graphql> in your browser (or use `curl`) to
query the indexed data with GraphQL.

Example:

```graphql
{{
  transfers(limit: 10) {{
    items {{
      id
      from
      to
      amount
    }}
  }}
}}
```

---

## Step 6 — Production deployment

For production, Ponder recommends PostgreSQL.  Set `DATABASE_URL` in your
environment (uncomment the line in `.env`) and run:

```bash
pnpm start
```

Or deploy to Railway, Render, Fly.io, etc. as a standard Node.js app.

---

## Quick reference

| Command      | Description                                      |
|--------------|--------------------------------------------------|
| `pnpm dev`   | Start indexer + GraphQL API with hot-reload      |
| `pnpm start` | Start indexer in production mode                 |
| `pnpm codegen` | Regenerate TypeScript types from schema        |

---

## Troubleshooting

**`Error: Invalid RPC URL`**
→ Check that `PONDER_RPC_URL_{{chainId}}` is set in `.env` and is a valid HTTPS URL.

**`SyntaxError` in generated handler code**
→ Regenerate from the canvas (some transforms may need manual adjustment for
   complex type combinations).

**Indexing stuck at 0%**
→ `startBlock` may be set too early.  Update `ponder.config.ts` to use the
   actual contract deployment block.

**BigDecimal fields show as text**
→ Ponder has no native arbitrary-precision decimal type.  BigDecimal fields
   are stored as text.  To do arithmetic, parse the value with a library such
   as `decimal.js`, or migrate the entity field to BigInt (store values in
   base units like wei).
"""
