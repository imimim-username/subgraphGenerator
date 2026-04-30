"""FastAPI server for the Subgraph Wizard visual node editor."""

import json
import logging
import re
import webbrowser
from pathlib import Path
from threading import Timer
from typing import Any

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="Subgraph Wizard", version="0.1.0")

# Path to the pre-built React frontend bundle
_STATIC_DIR = Path(__file__).parent / "static"


def _build_placeholder_html(port: int) -> str:
    """Return a minimal placeholder page shown before the React app is built."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Subgraph Wizard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-family: ui-monospace, "Cascadia Code", "Source Code Pro", monospace;
      background: #0f172a;
      color: #e2e8f0;
    }}
    h1 {{ font-size: 2rem; margin-bottom: 0.5rem; color: #7c3aed; }}
    p  {{ color: #94a3b8; margin: 0.25rem 0; }}
    .badge {{
      margin-top: 2rem;
      padding: 0.4rem 1rem;
      border: 1px solid #334155;
      border-radius: 9999px;
      font-size: 0.75rem;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <h1>Subgraph Wizard</h1>
  <p>Visual node editor — coming soon</p>
  <p>Server running on <strong>localhost:{port}</strong></p>
  <span class="badge">M1 skeleton &mdash; React app not yet built</span>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AbiParseRequest(BaseModel):
    abi: list  # raw ABI array from the client


class AbiFetchRequest(BaseModel):
    address: str
    network: str


class VisualConfig(BaseModel):
    """Full visual-config.json payload."""
    schema_version: int = 1
    subgraph_name: str = ""
    current_file: str | None = None   # name of the last-active canvas file (for session restore)
    output_mode: str = "graph"        # "graph" | "ponder"
    ponder_settings: dict[str, Any] = {}  # database, ordering, etc. — ponder mode only
    networks: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Config file helpers
# ---------------------------------------------------------------------------

# Default location; callers can override via ?dir= query param
_DEFAULT_CONFIG_DIR = Path.cwd()
_CONFIG_FILENAME = "visual-config.json"


def _config_path(directory: str | None) -> Path:
    base = Path(directory) if directory else _DEFAULT_CONFIG_DIR
    return base / _CONFIG_FILENAME


# ---------------------------------------------------------------------------
# Canvas library helpers
# ---------------------------------------------------------------------------

_CANVASES_DIR = _DEFAULT_CONFIG_DIR / "canvases"


def _get_canvases_dir() -> Path:
    _CANVASES_DIR.mkdir(parents=True, exist_ok=True)
    return _CANVASES_DIR


def _safe_name(name: str) -> str:
    """Sanitize a canvas name to a safe filename stem."""
    name = name.strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = name.lower().strip("-")
    return name or "untitled"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> JSONResponse:
    """Basic health check."""
    return JSONResponse({"status": "ok", "version": "0.1.0"})


@app.post("/api/abi/parse")
async def abi_parse(req: AbiParseRequest) -> JSONResponse:
    """Parse a raw ABI array and return events and read functions.

    The client uploads the ABI JSON (already parsed as a list). Returns:
      {"events": [...], "read_functions": [...]}
    """
    from subgraph_wizard.abi.utils import (
        validate_abi,
        extract_events,
        extract_read_functions,
    )
    from subgraph_wizard.errors import ValidationError

    try:
        validate_abi(req.abi)
        events = extract_events(req.abi)
        read_functions = extract_read_functions(req.abi)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return JSONResponse({"events": events, "read_functions": read_functions})


@app.post("/api/abi/fetch")
async def abi_fetch(req: AbiFetchRequest) -> JSONResponse:
    """Fetch a contract ABI from Etherscan and return events and read functions.

    Body: {"address": "0x...", "network": "ethereum"}
    Returns: {"abi": [...], "events": [...], "read_functions": [...]}
    """
    from subgraph_wizard.abi.etherscan import fetch_abi_from_explorer
    from subgraph_wizard.abi.utils import extract_events, extract_read_functions
    from subgraph_wizard.errors import AbiFetchError, ValidationError

    try:
        abi = fetch_abi_from_explorer(req.address, req.network)
        events = extract_events(abi)
        read_functions = extract_read_functions(abi)
    except (AbiFetchError, ValidationError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    return JSONResponse({"abi": abi, "events": events, "read_functions": read_functions})


@app.get("/api/config")
async def config_load(dir: str | None = Query(default=None)) -> JSONResponse:
    """Load visual-config.json from disk.

    Query params:
      dir  — directory that contains visual-config.json (default: cwd)

    Returns the parsed JSON object, or an empty scaffold if the file doesn't
    exist yet.
    """
    path = _config_path(dir)
    if not path.exists():
        return JSONResponse(
            {
                "schema_version": 1,
                "subgraph_name": "",
                "current_file": None,
                "output_mode": "graph",
                "ponder_settings": {},
                "networks": [],
                "nodes": [],
                "edges": [],
            }
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {e}")
    return JSONResponse(data)


@app.post("/api/config")
async def config_save(
    config: VisualConfig,
    dir: str | None = Query(default=None),
) -> JSONResponse:
    """Save visual-config.json to disk.

    Query params:
      dir  — directory to write visual-config.json into (default: cwd)

    Returns {"saved": true, "path": "…"} on success.
    """
    path = _config_path(dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")
    return JSONResponse({"saved": True, "path": str(path)})


@app.get("/api/canvases")
async def canvases_list() -> JSONResponse:
    """List all saved canvases, newest first.

    Returns a list of:
      { name, subgraph_name, node_count, updated_at (unix timestamp) }
    """
    d = _get_canvases_dir()
    result = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "name": f.stem,
                "subgraph_name": data.get("subgraph_name", ""),
                "node_count": len(data.get("nodes", [])),
                "updated_at": f.stat().st_mtime,
            })
        except Exception:
            pass
    return JSONResponse(result)


@app.get("/api/canvases/{name}")
async def canvas_load(name: str) -> JSONResponse:
    """Load a named canvas by name."""
    safe = _safe_name(name)
    path = _get_canvases_dir() / f"{safe}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Canvas '{safe}' not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to read canvas: {e}")
    return JSONResponse(data)


@app.post("/api/canvases/{name}")
async def canvas_save(name: str, config: VisualConfig) -> JSONResponse:
    """Save the current canvas under a given name."""
    safe = _safe_name(name)
    path = _get_canvases_dir() / f"{safe}.json"
    try:
        path.write_text(
            json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write canvas: {e}")
    return JSONResponse({"saved": True, "name": safe})


@app.delete("/api/canvases/{name}")
async def canvas_delete(name: str) -> JSONResponse:
    """Delete a named canvas."""
    safe = _safe_name(name)
    path = _get_canvases_dir() / f"{safe}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Canvas '{safe}' not found")
    path.unlink()
    return JSONResponse({"deleted": True, "name": safe})


@app.post("/api/simulate")
async def simulate(config: VisualConfig) -> JSONResponse:
    """Simulate a visual graph config and return a human-readable description.

    Body: VisualConfig
    Returns: {"handlers": [...], "schema": [...], "queries": [...]}
    """
    from subgraph_wizard.generate.graph_simulator import simulate_graph

    config_dict = config.model_dump()
    result = simulate_graph(config_dict)
    return JSONResponse(result)


@app.post("/api/validate")
async def validate(config: VisualConfig) -> JSONResponse:
    """Validate a visual graph config and return a list of issues.

    Body: VisualConfig
    Returns: {"issues": [...], "has_errors": bool}
    Each issue: {level, code, message, node_id, edge_id}
    """
    from subgraph_wizard.generate.validator import validate_graph, has_errors as _has_errors

    config_dict = config.model_dump()
    issues = validate_graph(config_dict)
    return JSONResponse({"issues": issues, "has_errors": _has_errors(issues)})


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

# Map Graph / internal types → GraphQL schema types
_GQL_TYPE: dict[str, str] = {
    "ID":         "ID",
    "String":     "String",
    "Bytes":      "Bytes",
    "Boolean":    "Boolean",
    "Int":        "Int",
    "BigInt":     "BigInt",
    "BigDecimal": "BigDecimal",
    "Address":    "Bytes",   # Address is stored as Bytes in the schema
}

# Set of primitive types; anything else is treated as an entity reference
_GQL_PRIMITIVES: frozenset[str] = frozenset(_GQL_TYPE.keys())


def _render_visual_schema(visual_config: dict[str, Any]) -> str:
    """Generate a schema.graphql string from entity and aggregateentity nodes.

    Handles three field flavours:
    1. Primitive type   → ``fieldName: GraphQLType[!]``
    2. Entity reference → ``fieldName: OtherEntityName[!]``
    3. @derivedFrom     → ``fieldName: [OtherEntityName!]! @derivedFrom(field: "xxx")``

    specVersion 1.0.0 requires every @entity to declare ``immutable``:
    - ``entity`` nodes         → ``@entity(immutable: true)``  (event logs, never updated)
    - ``aggregateentity`` nodes → ``@entity(immutable: false)`` (running totals, can be updated)

    When multiple canvas nodes share the same entity name (e.g. two contracts both
    emit a ``Deposit`` event), each is prefixed with its connected contract name so
    the generated types are distinct:
      AlchemistV3Deposit, TransmuterV3Deposit
    The same resolved names are used in subgraph.yaml and the mapping TypeScript.
    """
    from subgraph_wizard.generate.graph_compiler import build_entity_name_map

    nodes = visual_config.get("nodes", [])
    edges = visual_config.get("edges", [])
    name_map = build_entity_name_map(nodes, edges)  # {node_id: resolved_type_name}

    lines: list[str] = []
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

        immutable_str = "true" if node_type == "entity" else "false"
        lines.append(f"type {resolved_name} @entity(immutable: {immutable_str}) {{")

        seen_fields: set[str] = set()
        for f in data.get("fields", []):
            fname = f.get("name", "").strip()
            if not fname or fname in seen_fields:
                continue
            seen_fields.add(fname)
            ftype_raw = f.get("type", "String")
            derived_from = f.get("derivedFrom")

            if derived_from:
                lines.append(f'  {fname}: [{ftype_raw}!]! @derivedFrom(field: "{derived_from}")')
            elif ftype_raw in _GQL_PRIMITIVES:
                ftype = _GQL_TYPE.get(ftype_raw, "String")
                # graph codegen generates a conflicting TypeScript property when
                # id is typed as BigInt, Int, or Boolean — coerce to Bytes.
                if fname == "id" and ftype not in ("ID", "String", "Bytes"):
                    ftype = "Bytes"
                bang = "!" if f.get("required") or fname == "id" else ""
                lines.append(f"  {fname}: {ftype}{bang}")
            else:
                bang = "!" if f.get("required") or fname == "id" else ""
                lines.append(f"  {fname}: {ftype_raw}{bang}")

        lines.append("}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Start-block auto-detection via public JSON-RPC binary search
# ---------------------------------------------------------------------------

#: Public RPC endpoints for common EVM networks (no API key required)
_NETWORK_RPCS: dict[str, str] = {
    "mainnet":       "https://cloudflare-eth.com",
    "arbitrum-one":  "https://arb1.arbitrum.io/rpc",
    "base":          "https://mainnet.base.org",
    "optimism":      "https://mainnet.optimism.io",
    "polygon":       "https://polygon-rpc.com",
    "bnb":           "https://bsc-dataseed.binance.org",
    "avalanche":     "https://api.avax.network/ext/bc/C/rpc",
    "gnosis":        "https://rpc.gnosischain.com",
    "linea":         "https://rpc.linea.build",
    "scroll":        "https://rpc.scroll.io",
}


def _rpc(url: str, method: str, params: list) -> Any:
    """Synchronous JSON-RPC helper (run in a thread; uses requests)."""
    import requests as req_lib
    resp = req_lib.post(
        url,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")


def _detect_start_block_sync(address: str, network: str) -> int:
    """Binary-search for the first block where *address* has deployed code.

    Uses public JSON-RPC — no API key required.  Takes ~15-25 RPC calls
    (O(log currentBlock)).

    Returns the deployment block number, or 0 if the contract has no code
    at the current head (i.e. the address is wrong or not yet deployed).
    """
    rpc_url = _NETWORK_RPCS.get(network, _NETWORK_RPCS["mainnet"])

    # Current chain tip
    block_hex = _rpc(rpc_url, "eth_blockNumber", [])
    current_block = int(block_hex, 16)

    # Quick sanity-check: does the address have code at HEAD?
    head_code = _rpc(rpc_url, "eth_getCode", [address, "latest"])
    if not head_code or head_code == "0x":
        return 0  # no contract at this address on this network

    lo, hi = 0, current_block
    while lo < hi:
        mid = (lo + hi) // 2
        code = _rpc(rpc_url, "eth_getCode", [address, hex(mid)])
        if code and code != "0x":
            hi = mid
        else:
            lo = mid + 1

    return lo


@app.get("/api/detect-start-block")
async def detect_start_block(
    address: str = Query(..., description="Contract address (0x…)"),
    network: str = Query(default="mainnet", description="EVM network slug"),
) -> JSONResponse:
    """Detect the block number at which a contract was first deployed.

    Uses binary search over ``eth_getCode`` on a public RPC endpoint.
    Takes roughly 15-25 network round-trips (about 5-15 seconds).

    Returns:
      {"block": <int>, "address": "0x…", "network": "mainnet"}
    """
    import asyncio

    if not address or not address.startswith("0x"):
        raise HTTPException(status_code=400, detail="address must start with 0x")

    try:
        block = await asyncio.to_thread(_detect_start_block_sync, address, network)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RPC error: {exc}")

    return JSONResponse({"block": block, "address": address, "network": network})


@app.get("/api/fs/browse")
async def fs_browse(path: str | None = Query(default=None)) -> JSONResponse:
    """Return directory listing for the filesystem browser.

    Query params:
      path — absolute directory to list (defaults to user home directory)

    Returns:
      {
        "path": "/current/abs/path",
        "parent": "/parent/path" | null,
        "dirs": [{"name": "foo", "path": "/current/abs/path/foo"}, ...]
      }
    """
    start = Path(path).expanduser().resolve() if path else Path.home()
    # Clamp to an existing directory
    if not start.is_dir():
        start = start.parent if start.parent.is_dir() else Path.home()

    try:
        entries = sorted(
            (e for e in start.iterdir() if e.is_dir() and not e.name.startswith(".")),
            key=lambda e: e.name.lower(),
        )
    except PermissionError:
        entries = []

    parent = str(start.parent) if start.parent != start else None  # None at filesystem root

    return JSONResponse({
        "path": str(start),
        "parent": parent,
        "dirs": [{"name": e.name, "path": str(e)} for e in entries],
    })


@app.post("/api/fs/mkdir")
async def fs_mkdir(body: dict = Body(...)) -> JSONResponse:
    """Create a new directory (and any missing parents).

    Body: {"path": "/full/path/to/new/dir"}
    Returns: {"path": "/full/path/to/new/dir"}
    """
    raw_path = body.get("path", "")
    if not raw_path or not raw_path.strip():
        raise HTTPException(status_code=400, detail="Invalid path")
    target = Path(raw_path).expanduser().resolve()
    if not target.name:
        raise HTTPException(status_code=400, detail="Invalid path")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse({"path": str(target)})


@app.post("/api/generate")
async def generate(
    config: VisualConfig,
    dir: str | None = Query(default=None),
) -> JSONResponse:
    """Compile the visual graph and write output files to disk.

    Body: VisualConfig (same as POST /api/config)
    Query params:
      dir  — output directory (default: cwd)

    Returns {"files": ["path1", "path2", ...], "dir": "<output_dir>"} on success.

    When config.output_mode == "ponder", generates a Ponder TypeScript project
    instead of a Graph Protocol subgraph.
    """
    output_dir = Path(dir) if dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    config_dict = config.model_dump()
    subgraph_name = config.subgraph_name or "my-subgraph"
    output_mode = config.output_mode or "graph"
    written: list[str] = []

    try:
        # Always write visual-config.json alongside the generated output
        config_path = output_dir / "visual-config.json"
        config_path.write_text(
            json.dumps(config_dict, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written.append(str(config_path))

        if output_mode == "ponder":
            written.extend(_generate_ponder(config_dict, subgraph_name, output_dir))
        else:
            written.extend(
                await _generate_graph(config_dict, subgraph_name, output_dir)
            )

    except Exception as e:
        logger.exception("generate error")
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse({"files": written, "dir": str(output_dir)})


async def _generate_graph(
    config_dict: dict[str, Any],
    subgraph_name: str,
    output_dir: Path,
) -> list[str]:
    """Write a full Graph Protocol subgraph project to *output_dir*.

    Returns the list of written file paths.
    """
    from subgraph_wizard.generate.graph_compiler import compile_graph
    from subgraph_wizard.generate.networks_json import write_networks_json
    from subgraph_wizard.generate.subgraph_yaml import render_visual_subgraph_yaml
    import asyncio as _asyncio

    written: list[str] = []

    # networks.json
    networks = config_dict.get("networks", [])
    if networks:
        nj_path = write_networks_json(networks, output_dir)
        written.append(str(nj_path))

    # Auto-detect missing startBlocks, then write subgraph.yaml
    _detections: list[tuple] = []  # (node_index, address, network)
    for _i, _node in enumerate(config_dict.get("nodes", [])):
        if _node.get("type") != "contract":
            continue
        _d = _node.get("data", {})
        _addr = _d.get("address", "").strip()
        _sb = _d.get("startBlock", 0)
        try:
            _sb_int = int(_sb or 0)
        except (ValueError, TypeError):
            _sb_int = 0
        if _addr.startswith("0x") and _sb_int == 0:
            _net = _d.get("network", "mainnet") or "mainnet"
            _detections.append((_i, _addr, _net))

    if _detections:
        tasks = [
            _asyncio.to_thread(_detect_start_block_sync, addr, net)
            for (_, addr, net) in _detections
        ]
        _results = await _asyncio.gather(*tasks, return_exceptions=True)
        for (idx, _a, _n), result in zip(_detections, _results):
            if isinstance(result, int) and result > 0:
                config_dict["nodes"][idx]["data"]["startBlock"] = result
                logger.info(f"Auto-detected startBlock={result} for {_a} on {_n}")

    yaml_content = render_visual_subgraph_yaml(config_dict)
    yaml_path = output_dir / "subgraph.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    written.append(str(yaml_path))

    # schema.graphql
    schema_content = _render_visual_schema(config_dict)
    schema_path = output_dir / "schema.graphql"
    schema_path.write_text(schema_content, encoding="utf-8")
    written.append(str(schema_path))

    # ABI JSON files
    abis_dir = output_dir / "abis"
    abis_dir.mkdir(parents=True, exist_ok=True)
    for node in config_dict.get("nodes", []):
        if node.get("type") != "contract":
            continue
        contract_name = node.get("data", {}).get("name", "").strip()
        abi_data = node.get("data", {}).get("abi")
        if contract_name and abi_data:
            abi_path = abis_dir / f"{contract_name}.json"
            abi_path.write_text(
                json.dumps(abi_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            written.append(str(abi_path))

    # AssemblyScript mapping files
    as_files = compile_graph(config_dict)
    if as_files:
        mappings_dir = output_dir / "src" / "mappings"
        mappings_dir.mkdir(parents=True, exist_ok=True)
        for contract_type, source in as_files.items():
            ts_path = mappings_dir / f"{contract_type}.ts"
            ts_path.write_text(source, encoding="utf-8")
            written.append(str(ts_path))

    # package.json
    pkg_json = _render_package_json(subgraph_name)
    pkg_path = output_dir / "package.json"
    pkg_path.write_text(pkg_json, encoding="utf-8")
    written.append(str(pkg_path))

    # howto.md
    howto_content = _render_howto_md(subgraph_name, str(output_dir))
    howto_path = output_dir / "howto.md"
    howto_path.write_text(howto_content, encoding="utf-8")
    written.append(str(howto_path))

    return written


def _generate_ponder(
    config_dict: dict[str, Any],
    subgraph_name: str,
    output_dir: Path,
) -> list[str]:
    """Write a full Ponder TypeScript indexer project to *output_dir*.

    Returns the list of written file paths.
    """
    from subgraph_wizard.generate.ponder_compiler import compile_ponder, render_abi_ts
    from subgraph_wizard.generate.ponder_schema import render_ponder_schema
    from subgraph_wizard.generate.ponder_config import (
        render_ponder_config,
        render_ponder_env_dts,
        render_ponder_tsconfig,
        render_ponder_package_json,
        render_ponder_env_example,
        render_ponder_howto,
    )

    written: list[str] = []

    # ponder.config.ts
    ponder_cfg = render_ponder_config(config_dict)
    (output_dir / "ponder.config.ts").write_text(ponder_cfg, encoding="utf-8")
    written.append(str(output_dir / "ponder.config.ts"))

    # ponder.schema.ts
    ponder_schema = render_ponder_schema(config_dict)
    (output_dir / "ponder.schema.ts").write_text(ponder_schema, encoding="utf-8")
    written.append(str(output_dir / "ponder.schema.ts"))

    # ponder-env.d.ts
    (output_dir / "ponder-env.d.ts").write_text(render_ponder_env_dts(), encoding="utf-8")
    written.append(str(output_dir / "ponder-env.d.ts"))

    # tsconfig.json
    (output_dir / "tsconfig.json").write_text(render_ponder_tsconfig(), encoding="utf-8")
    written.append(str(output_dir / "tsconfig.json"))

    # package.json
    (output_dir / "package.json").write_text(
        render_ponder_package_json(subgraph_name), encoding="utf-8"
    )
    written.append(str(output_dir / "package.json"))

    # .env.example
    (output_dir / ".env.example").write_text(
        render_ponder_env_example(config_dict), encoding="utf-8"
    )
    written.append(str(output_dir / ".env.example"))

    # PONDER_HOWTO.md
    (output_dir / "PONDER_HOWTO.md").write_text(
        render_ponder_howto(subgraph_name, str(output_dir)), encoding="utf-8"
    )
    written.append(str(output_dir / "PONDER_HOWTO.md"))

    # ABI TypeScript files  (abis/<ContractName>Abi.ts)
    abis_dir = output_dir / "abis"
    abis_dir.mkdir(parents=True, exist_ok=True)
    for node in config_dict.get("nodes", []):
        if node.get("type") != "contract":
            continue
        contract_name = node.get("data", {}).get("name", "").strip()
        abi_data = node.get("data", {}).get("abi")
        if contract_name and abi_data:
            abi_ts = render_abi_ts(contract_name, abi_data)
            abi_path = abis_dir / f"{contract_name}Abi.ts"
            abi_path.write_text(abi_ts, encoding="utf-8")
            written.append(str(abi_path))

    # src/index.ts  (event handlers) — compile_ponder keys include the "src/" prefix
    ts_files = compile_ponder(config_dict)
    for rel_path, content in ts_files.items():
        file_path = output_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        written.append(str(file_path))

    return written


def _render_package_json(subgraph_name: str) -> str:
    """Return a package.json suitable for a Graph Protocol subgraph."""
    slug = subgraph_name.lower().replace(" ", "-")
    pkg = {
        "name": slug,
        "version": "0.0.1",
        "scripts": {
            "codegen": "graph codegen",
            "build": "graph build",
            "deploy": f"graph deploy --studio {slug}",
            "create-local": f"graph create --node http://localhost:8020/ {slug}",
            "deploy-local": (
                f"graph deploy --node http://localhost:8020/ "
                f"--ipfs http://localhost:5001 {slug}"
            ),
        },
        "dependencies": {
            "@graphprotocol/graph-cli": "latest",
            "@graphprotocol/graph-ts": "latest",
        },
    }
    return json.dumps(pkg, indent=2, ensure_ascii=False)


def _render_howto_md(subgraph_name: str, output_dir: str) -> str:
    """Return a detailed deployment guide for The Graph."""
    slug = subgraph_name.lower().replace(" ", "-")
    return f"""\
# How to Deploy "{subgraph_name}" to The Graph

This guide walks you through every step needed to build and deploy your
subgraph to The Graph's Subgraph Studio — from a completely clean machine.

---

## Step 1 — Install Node.js

The Graph CLI requires **Node.js 18 or later**.

### macOS / Linux — recommended: use nvm

```bash
# Install nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Close and reopen your terminal, then run:
nvm install 20
nvm use 20
nvm alias default 20

# Verify
node --version   # should print v20.x.x
npm --version    # should print 10.x.x
```

### macOS — alternative: direct download

Download the macOS installer from <https://nodejs.org/en/download/> (choose
the **LTS** version) and run the `.pkg` file.

### Windows

Download the Windows installer from <https://nodejs.org/en/download/> (choose
the **LTS** version) and run the `.msi` file. Ensure **"Add to PATH"** is
checked during installation.

---

## Step 2 — Install The Graph CLI

```bash
npm install -g @graphprotocol/graph-cli
```

Verify the installation:

```bash
graph --version
```

You should see something like `@graphprotocol/graph-cli/0.x.x`.

---

## Step 3 — Install Project Dependencies

Navigate to your output directory and install the project's Node dependencies:

```bash
cd "{output_dir}"
npm install
```

This installs `@graphprotocol/graph-ts` (AssemblyScript types) and the Graph
CLI locally, as listed in `package.json`.

> **Note on deprecation warnings:** `npm install` may print warnings about
> deprecated packages such as `inflight`, `rimraf`, and `glob`. These come
> from inside `@graphprotocol/graph-cli`'s own dependency tree — they are
> **not** from your project and are safe to ignore. The install still succeeds
> and everything works correctly.

---

## Step 4 — Review and Finalize `subgraph.yaml`

The ABI files for each contract have already been written to the `abis/`
directory by the generator — you don't need to source them manually.

Open `subgraph.yaml` in a text editor and fill in the two remaining fields
for each data source:

| Field | What to verify |
|---|---|
| `network` | Matches the network your contracts are on (e.g. `mainnet`, `arbitrum-one`, `base`) |
| `address` | The deployed contract address (checksummed, `0x…`) |
| `startBlock` | The block number the contract was **first deployed** at — using the correct block avoids unnecessary re-indexing |
| `abis[*].file` | Points to the correct file in your `abis/` directory |

---

## Step 5 — Create a Subgraph Studio Account

1. Go to <https://thegraph.com/studio/>
2. Click **Connect Wallet** and connect your Ethereum wallet.
   - If you don't have a wallet, install MetaMask from
     <https://metamask.io/download/> (browser extension).
3. You are now in Subgraph Studio.

---

## Step 6 — Create a New Subgraph in Studio

1. In Subgraph Studio, click **Create a Subgraph**.
2. Enter a name — this becomes your **subgraph slug** (e.g. `{slug}`).
3. Select the network your contracts are deployed on.
4. Click **Create Subgraph**.

---

## Step 7 — Get Your Deploy Key

1. On your subgraph's page in Subgraph Studio, go to the **Details** tab.
2. Copy the **Deploy Key** shown (a long hex string starting with `0x…`).

---

## Step 8 — Authenticate the Graph CLI

Back in your terminal:

```bash
graph auth --studio <YOUR_DEPLOY_KEY>
```

Replace `<YOUR_DEPLOY_KEY>` with the key copied in Step 7. You only need to
do this once per machine.

---

## Step 9 — Generate TypeScript Type Bindings

The Graph CLI reads your `schema.graphql` and ABI files to auto-generate
AssemblyScript type bindings used by the mapping code:

```bash
graph codegen
```

This creates a `generated/` folder. If it fails, check that the ABI file
paths in `subgraph.yaml` exist and match exactly.

---

## Step 10 — Build the Subgraph

Compile your AssemblyScript mapping files to WebAssembly:

```bash
graph build
```

A successful build produces a `build/` directory. Fix any compiler errors
before continuing — common issues:
- Importing a type that doesn't exist in `generated/` (re-run `graph codegen`)
- Calling a method on a nullable value without a null-check

---

## Step 11 — Deploy to Subgraph Studio

```bash
graph deploy --studio {slug}
```

You will be prompted for a **version label** — use semantic versioning:

```
Version Label (e.g. v0.0.1): v0.0.1
```

The CLI uploads your subgraph to IPFS and registers it in Studio. Deployment
typically takes under a minute.

---

## Step 12 — Monitor Indexing

1. Open your subgraph in Subgraph Studio: <https://thegraph.com/studio/>
2. The **Overview** tab shows the **Sync Status** and current block.
3. Once fully synced, test queries in the **Playground** tab using GraphQL.

If indexing errors appear, check the **Logs** tab. Common causes:
- **ABI mismatch** — the ABI in `abis/` doesn't match what was deployed
  on-chain (e.g. using a proxy ABI instead of the implementation ABI)
- **Wrong start block** — set `startBlock` closer to contract deployment
- **Handler not found** — event name in `subgraph.yaml` doesn't match ABI

---

## Step 13 — Publish to the Decentralized Network (optional)

Once you're satisfied with your subgraph in Studio, you can publish it to
The Graph's decentralized network so indexers can serve it:

1. In Subgraph Studio, click **Publish to Decentralized Network**.
2. You need **GRT tokens** to signal on your subgraph (GRT is The Graph's
   native token, available on Coinbase, Binance, Uniswap, etc.).
3. Publishing costs a small amount of ETH (gas) on Arbitrum.
4. After publishing, your subgraph endpoint moves from a Studio-only URL to
   a decentralized query URL.

> **Note:** For most development and testing purposes, the Studio endpoint
> (available immediately after Step 11) is sufficient. Publishing to the
> decentralized network is the step needed for production use.

---

## Quick Reference

```bash
# One-time setup (do once per machine)
npm install -g @graphprotocol/graph-cli
graph auth --studio <YOUR_DEPLOY_KEY>

# Per-deployment workflow
cd "{output_dir}"
npm install
graph codegen
graph build
graph deploy --studio {slug}
```

| Command | Description |
|---|---|
| `graph codegen` | Generate TypeScript bindings from schema + ABIs |
| `graph build` | Compile mappings to WebAssembly |
| `graph deploy --studio <slug>` | Deploy to Subgraph Studio |
| `graph auth --studio <key>` | Save your deploy key (once per machine) |
| `graph --help` | Show all available commands |

---

## Troubleshooting

**`graph: command not found`**
→ The CLI isn't on your PATH. Try `npx @graphprotocol/graph-cli <command>`,
  or reinstall: `npm install -g @graphprotocol/graph-cli`

**`Cannot find module '@graphprotocol/graph-ts'`**
→ Run `npm install` in the project directory.

**`ENOENT` — ABI file not found**
→ Verify each `abis[*].file` path in `subgraph.yaml` exists on disk.

**`graph codegen` produces no output / errors**
→ Check that `schema.graphql` is valid and that your ABI JSON files are
  well-formed arrays (not wrapped in an object with a `"abi"` key).

**TS2322 type error during `graph build`**

Example:
```
ERROR TS2322: Type 'Bytes' is not assignable to type 'Array<BigInt> | null'
   entity.accounts = event.params.accounts
```

→ An entity field type does not match the event parameter type.
  The visual editor now catches this at generate time and reports it as a
  clear error — if you see it in `graph build`, you are building files
  generated by an older version. Regenerate from the canvas, then fix the
  entity field type to match the event param type (or use a Type Cast node
  for intentional conversions).

**Indexed array parameter is `Bytes` instead of the expected array type**
→ In Ethereum event logs, `indexed` parameters of reference types (any
  array, `bytes`, `string`, tuple) are stored only as their keccak256 hash —
  the actual value is not recoverable on-chain. graph-cli generates `Bytes`
  for these. Your entity field must also be `Bytes`. If you need the actual
  array values, use non-indexed parameters or per-item events.

**Fields are null / wrong value in the deployed subgraph**
→ Two common causes:
  1. An unwired entity field whose name doesn't match any event parameter
     (auto-fill is name-matching and case-sensitive).
  2. The contract address was not entered in the **Networks panel** — the
     compiler reads the address from there, not from the inline address box
     on the Contract node.

**Entity field type is stale after re-parsing the ABI**
→ Re-parsing the ABI updates the Contract node's port types but does NOT
  retroactively update field types on Entity nodes you already created.
  Go to the Entity node and manually update any affected field types using
  the type dropdown and the `[ ]` list-mode toggle.

**Indexing errors in Studio → Logs tab**
→ Look for `Unexpected token`, `Store error`, or `mapping error`. These
  indicate an ABI mismatch, a null-pointer in a handler, or a type mismatch
  in entity field assignments.

**Subgraph stuck at 0% sync or syncing from block 0**
→ The `startBlock` in the Networks panel was not set or was left at 0. Set
  it to the block your contract was first deployed at — visible on the block
  explorer as the "Contract Creation" transaction block number. Indexing from
  block 0 forces The Graph to process the entire chain history, which can
  take days.
"""


@app.get("/", response_class=HTMLResponse)
async def root(port: int = 5173) -> HTMLResponse:
    """
    Serve the React app's index.html if it exists, otherwise a placeholder.
    FastAPI's StaticFiles mount (added in start_server) handles all other
    static assets once the frontend is built.
    """
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text())
    return HTMLResponse(_build_placeholder_html(port))


def _mount_static_if_built() -> None:
    """Mount the pre-built React bundle if it exists."""
    if _STATIC_DIR.exists() and any(_STATIC_DIR.iterdir()):
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
        logger.info(f"Serving pre-built frontend from {_STATIC_DIR}")
    else:
        logger.info("No pre-built frontend found — serving placeholder page")


def start_server(port: int = 5173, open_browser: bool = True) -> None:
    """
    Start the uvicorn server and optionally open the browser.

    Args:
        port: TCP port to listen on.
        open_browser: If True, open http://localhost:{port} after a short delay.
    """
    _mount_static_if_built()

    url = f"http://localhost:{port}"
    print(f"\n  Subgraph Wizard  →  {url}\n")

    if open_browser:
        # Give uvicorn a moment to bind before opening the browser
        Timer(1.0, webbrowser.open, args=(url,)).start()

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
