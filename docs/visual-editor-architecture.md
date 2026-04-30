# Visual Node Editor — Architecture

## Overview

The Subgraph Wizard offers a local web-based visual node editor alongside the
original CLI wizard. The user launches it with:

```bash
subgraph-wizard --ui          # opens http://localhost:5173 automatically
subgraph-wizard --ui --port 8080     # custom port
subgraph-wizard --ui --no-browser    # headless
```

The browser opens a React canvas where the user wires contract events to entity
fields. Clicking **Generate** produces working AssemblyScript mapping files, a
`subgraph.yaml`, `networks.json`, and `schema.graphql` — a complete subgraph
ready for `graph build`.

---

## High-Level Architecture

```
Browser (React + React Flow)
        │
        │  HTTP / JSON   (Vite proxy in dev: /api → :8000)
        ▼
FastAPI server  (src/subgraph_wizard/server.py)
        │
        ├── ABI parse / fetch   (abi/ package)
        ├── Graph validator      (generate/validator.py)
        ├── Graph compiler       (generate/graph_compiler.py)
        ├── subgraph.yaml render (generate/subgraph_yaml.py)
        └── networks.json writer (generate/networks_json.py)
```

### Dev workflow

Two terminals:

```bash
# Terminal 1 — backend (FastAPI on port 8000)
uvicorn subgraph_wizard.server:app --port 8000 --reload

# Terminal 2 — frontend (Vite dev server on port 5173, proxies /api → :8000)
cd frontend && npm run dev
```

Override the backend port with `VITE_API_PORT`:

```bash
VITE_API_PORT=9000 npm run dev
```

### Production (end-user)

`subgraph-wizard --ui` starts uvicorn on port 5173 and serves the pre-built
React bundle from `src/subgraph_wizard/static/`. No Node.js required.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend framework | React + Vite |
| Node editor | React Flow (`@xyflow/react`) |
| Styling | Tailwind CSS v4 (via `@tailwindcss/vite`) |
| Backend | FastAPI + uvicorn |
| State persistence | JSON file on disk (`visual-config.json`) |

> **Note:** shadcn/ui is not used. All UI components are hand-rolled with
> Tailwind.

---

## Node Types

### `contract`
Root node. The user provides:
- **Contract type name** (logical name shared across all deployed instances)
- **ABI** — uploaded, pasted, or fetched from Etherscan via `/api/abi/fetch`

**Output ports** (auto-generated from ABI):
- `event-{EventName}` — one port per ABI event (carries the whole event; used
  only to establish which handler a dependency belongs to)
- `event-{EventName}-{paramName}` — one port per event parameter
- `implicit-address` — `event.address` (Address/Bytes)
- `implicit-block-number` — `event.block.number` (BigInt)
- `implicit-block-timestamp` — `event.block.timestamp` (BigInt)
- `implicit-tx-hash` — `event.transaction.hash` (Bytes)

There is **no separate Event node**. Event params are output ports directly on
the Contract node.

### `entity`
GraphQL entity. User defines the entity name and its fields.

**Input ports:**
- `field-{name}` — one per field; the `id` field is always present and required

### `math`
BigInt binary arithmetic (add / subtract / multiply / divide / mod / pow).

- **Inputs:** `left`, `right` (both BigInt)
- **Output:** `result` (BigInt)

### `typecast`
Type conversion between Graph types. The `castIndex` integer selects the cast:

| Index | From | To | AS expression |
|---|---|---|---|
| 0 | BigInt | Int | `.toI32()` |
| 1 | BigInt | String | `.toString()` |
| 2 | Bytes | String | `.toHexString()` |
| 3 | Bytes | Address | `Address.fromBytes()` |
| 4 | String | Bytes | `Bytes.fromHexString()` |
| 5 | Address | String | `.toHexString()` |
| 6 | Address | Bytes | `changetype<Bytes>()` |

- **Input:** `value`
- **Output:** `result`

### `strconcat`
String concatenation with an optional separator.

- **Inputs:** `left`, `right` (both String)
- **Output:** `result` (String)

### `conditional`
Boolean guard. If the condition is falsy the handler returns early.

- **Inputs:** `condition` (Boolean), `value` (any)
- **Output:** `value-out` (passes through)

### `contractread`
Calls a view function on-chain inside an event handler using the Graph's
generated contract bindings.

- **Data:** `contractNodeId` (references a `contract` node), `fnIndex`
- **Inputs:** `in-{argName}` — one per function argument
- **Outputs:** `out-{retName}` — one per return value

### `aggregateentity`
Running-total / cumulative entity. Uses a stable key to load the same record
across many events and accumulate field values. Rendered with a deep-blue
header and a LayoutGrid icon.

**Input ports (left side):**
- `field-id` — target; the stable key expression (e.g. a string literal or
  contract address) used to load-or-create the same row every time
- `field-in-{name}` — target; the new value to write into field `{name}` on
  this event

**Output ports (right side):**
- `field-prev-{name}` — source; the value of field `{name}` **before** the
  current update (captured as `{var}_prev_{name}` in compiled output)

**Compilation pattern:**

1. Load-or-create with type-aware zero initialisation (`BigInt.fromI32(0)`,
   `BigDecimal.fromString('0')`, `""` for String/ID, etc.)
2. Capture previous values: `let {var}_prev_{name} = {var}.{name}`
3. Write new values from wired `field-in-{name}` edges
4. Save

The aggregate block is always emitted **before** regular `entity` blocks in
the same handler so that `field-prev-{name}` values are available to
downstream nodes.

---

## Networks Panel

A right-side panel (collapsible). For each network the user adds contract
instance rows (label, address, startBlock). This data is stored in the
`networks` array in `visual-config.json` and written to `networks.json` on
generate.

---

## Graph State Format (`visual-config.json`)

```json
{
  "schema_version": 1,
  "subgraph_name": "my-alchemix-subgraph",
  "networks": [
    {
      "network": "mainnet",
      "contracts": {
        "Alchemist": {
          "instances": [
            { "label": "alUSD", "address": "0xAAA...", "startBlock": 14265505 },
            { "label": "alETH", "address": "0xBBB...", "startBlock": 14265505 }
          ]
        }
      }
    },
    {
      "network": "arbitrum",
      "contracts": {
        "Alchemist": {
          "instances": [
            { "label": "alUSD", "address": "0xCCC...", "startBlock": 50000000 }
          ]
        }
      }
    }
  ],
  "nodes": [
    {
      "id": "contract-1",
      "type": "contract",
      "position": { "x": 100, "y": 200 },
      "data": {
        "name": "Alchemist",
        "abi": ["..."],
        "events": ["..."],
        "readFunctions": ["..."],
        "instances": [{ "label": "alUSD", "address": "", "startBlock": 0 }]
      }
    },
    {
      "id": "entity-1",
      "type": "entity",
      "position": { "x": 600, "y": 200 },
      "data": {
        "name": "TransferEvent",
        "fields": [
          { "name": "id",     "type": "ID",    "required": true },
          { "name": "from",   "type": "Bytes",  "required": false },
          { "name": "amount", "type": "BigInt", "required": false }
        ]
      }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "contract-1", "sourceHandle": "event-Transfer-from",
      "target": "entity-1",   "targetHandle": "field-from"
    }
  ]
}
```

> **Key difference from the original design:** `networks` is a **list** of
> `{network, contracts}` objects, not a dict keyed by network name.

---

## FastAPI Backend API (`server.py`)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Basic health check; returns `{status, version}` |
| `POST` | `/api/abi/parse` | Parse raw ABI JSON; returns `{events, read_functions}` |
| `POST` | `/api/abi/fetch` | Fetch ABI from Etherscan by address + network; returns `{abi, events, read_functions}` |
| `GET` | `/api/config` | Load `visual-config.json` from disk (scaffold if missing) |
| `POST` | `/api/config` | Save `visual-config.json` to disk; returns `{saved, path}` |
| `POST` | `/api/validate` | Validate graph; returns `{issues, has_errors}` |
| `POST` | `/api/generate` | Compile graph → write output files; returns `{files}` |
| `GET` | `/` | Serve React `index.html` (or placeholder if not built) |

All endpoints accept an optional `?dir=<path>` query param to specify which
directory to read/write config and output files (default: `cwd`).

> **Note:** The ABI endpoint is `/api/abi/parse` (not `/api/abi/upload` as in
> the original design doc).

---

## Graph Validator (`generate/validator.py`)

`validate_graph(visual_config)` returns a list of issue objects:

```python
{
  "level":   "error" | "warning",
  "code":    str,        # machine-readable, e.g. "ENTITY_NO_ID_WIRED"
  "message": str,        # human-readable
  "node_id": str | None,
  "edge_id": str | None,
}
```

### Error codes (block generation)

| Code | Trigger |
|---|---|
| `CONTRACT_NO_NAME` | Contract node has no type name |
| `CONTRACT_NO_ABI` | Contract node has no ABI loaded |
| `ENTITY_NO_NAME` | Entity node has no name |
| `ENTITY_NO_ID_WIRED` | Entity `id` field has no incoming edge |
| `TYPE_MISMATCH` | Edge connects ports with incompatible Graph types |
| `CONTRACTREAD_NO_CONTRACT` | ContractRead references a missing/unselected contract |
| `CONTRACTREAD_BAD_FN_INDEX` | ContractRead `fnIndex` out of range |
| `AGGREGATE_NO_NAME` | Aggregate entity node has no name |
| `AGGREGATE_NO_ID_WIRED` | Aggregate entity `field-id` port has no incoming edge |

### Warning codes (generation continues)

| Code | Trigger |
|---|---|
| `CONTRACT_EMPTY_INSTANCE` | A contract instance row has no address |
| `ENTITY_NO_FIELDS` | Entity has non-id fields but none are wired |
| `DISCONNECTED_CONTRACT` | Contract has events but none are wired to any entity |
| `DISCONNECTED_ENTITY` | Entity has no incoming connections |
| `MATH_DISCONNECTED_INPUT` | Math node has an unwired `left` or `right` port |
| `STRCONCAT_DISCONNECTED` | String Concat node has an unwired `left` or `right` port |
| `CONDITIONAL_NO_CONDITION` | Conditional node `condition` port not wired |
| `TYPECAST_BAD_INDEX` | TypeCast `castIndex` out of valid range (0–6) |
| `AGGREGATE_NO_FIELDS` | Aggregate entity has no `field-in-*` wires (accumulates nothing) |
| `DISCONNECTED_AGGREGATE` | Aggregate entity node has no incoming connections |

### Type compatibility table

The validator uses this table to check edge type compatibility:

| Source type | Compatible targets |
|---|---|
| BigInt | BigInt |
| Int | Int, BigInt |
| BigDecimal | BigDecimal |
| Bytes | Bytes, Address, String, ID |
| Address | Address, Bytes, String, ID |
| String | String, ID |
| Boolean | Boolean |
| ID | ID, String |
| any | (wildcard — matches everything) |

---

## Graph Compiler (`generate/graph_compiler.py`)

`compile_graph(visual_config)` → `dict[contract_type, AssemblyScript source]`

### Algorithm (per event handler)

1. Find all Entity nodes with at least one incoming edge from this event's
   output ports
2. For each Entity node, topologically traverse its dependency graph backwards
   through Math / TypeCast / StringConcat / Conditional / ContractRead nodes
   until reaching event params or implicit ports
3. Emit variable declarations in dependency order
4. Emit `loadOrCreate` call + field assignments
5. Wrap in handler boilerplate

### Port ID conventions

| Node type | Port direction | Port ID format |
|---|---|---|
| contract | output (event) | `event-{EventName}`, `event-{EventName}-{paramName}` |
| contract | output (implicit) | `implicit-address`, `implicit-block-number`, `implicit-block-timestamp`, `implicit-tx-hash` |
| entity | input | `field-{name}` |
| math | input | `left`, `right` |
| math | output | `result` |
| typecast | input | `value` |
| typecast | output | `result` |
| strconcat | input | `left`, `right` |
| strconcat | output | `result` |
| conditional | input | `condition`, `value` |
| conditional | output | `value-out` |
| contractread | input | `in-{argName}` |
| contractread | output | `out-{retName}` |
| aggregateentity | input | `field-id`, `field-in-{name}` |
| aggregateentity | output | `field-prev-{name}` |

---

## Frontend Architecture (`frontend/`)

### Key files

| File | Purpose |
|---|---|
| `src/App.jsx` | Main canvas; node/edge state; save/load/generate logic |
| `src/nodes/ContractNode.jsx` | ABI upload/fetch, event+read ports, multi-instance |
| `src/nodes/EntityNode.jsx` | Field ports, ID strategy |
| `src/nodes/MathNode.jsx` | BigInt arithmetic |
| `src/nodes/TypeCastNode.jsx` | Type conversion |
| `src/nodes/StringConcatNode.jsx` | String concatenation |
| `src/nodes/ConditionalNode.jsx` | Boolean guard |
| `src/nodes/ContractReadNode.jsx` | On-chain view function call |
| `src/nodes/AggregateEntityNode.jsx` | Running-total entity (deep-blue header, LayoutGrid icon) |
| `src/hooks/useValidation.js` | Debounced POST /api/validate; returns issue maps |
| `src/components/ValidationPanel.jsx` | Collapsible bottom-left issues list |
| `src/components/NetworksPanel.jsx` | Right-side panel for chain addresses |
| `src/components/Toolbar.jsx` | Left-side node palette; includes buttons for Contract, Entity, Math, TypeCast, StringConcat, Conditional, ContractRead, and Aggregate Entity |

### Validation wiring

`useValidation(nodes, edges)` debounces 600 ms then POSTs to `/api/validate`.
Returns:
- `issues` — full array
- `hasErrors` — boolean
- `issuesByNodeId` — `Map<nodeId, issue[]>` for node highlighting
- `issuesByEdgeId` — `Map<edgeId, issue[]>` for edge highlighting
- `isValidating` — boolean

`App.jsx` uses `useMemo` to derive `displayNodes` and `displayEdges` from the
canonical React Flow state plus validation maps, attaching CSS classNames
(`has-validation-error`, `has-validation-warning`) and edge stroke colors
without mutating canonical state.

### Save / Load / Generate

- **On mount:** `GET /api/config` — loads existing `visual-config.json` if
  present; `rehydrateNode()` re-attaches `onChange` callbacks stripped during
  JSON serialization
- **Save:** `POST /api/config` with current canvas state
- **Generate:** `POST /api/generate` — disabled while `hasErrors === true`;
  server writes all output files and returns the list of paths

---

## Generated Output Structure

```
<output-dir>/
├── visual-config.json         ← saved graph state (re-open in UI)
├── subgraph.yaml              ← mustache-templated; use with networks.json
├── networks.json              ← per-chain addresses + start blocks
└── src/
    └── mappings/
        └── {ContractType}.ts  ← compiled AssemblyScript handler
```

`schema.graphql` is generated automatically from the visual graph. On
`POST /api/generate`, the server calls `_render_visual_schema` (in
`server.py`) which inspects all `entity` and `aggregateentity` nodes and
emits a complete GraphQL schema. The file is written alongside the other
output files in the output directory.

---

## Python Package Bundling

The pre-built React bundle (`npm run build`) outputs to
`src/subgraph_wizard/static/`. This directory is included in the Python wheel
via `pyproject.toml`:

```toml
[tool.setuptools.package-data]
subgraph_wizard = [
    "static/**/*",
    "templates/**/*.j2",
]
```

End users get a fully working UI via `pip install` with no Node.js required.
Contributors must rebuild the frontend after changes:

```bash
cd frontend && npm install && npm run build
```

---

## Decisions (as implemented)

1. **No separate Event node.** Event parameters are output ports directly on
   the Contract node. There is no "Event node" type in the actual codebase
   (it was removed during implementation in favour of this simpler model).

2. **CLI wizard preserved.** `interactive_wizard.py`, `--config`, and
   `--generate` flags are still present and functional. The visual editor is
   an additional mode, not a replacement.

3. **Networks format is a list, not a dict.** `visual-config.json` stores
   `networks` as `list[{network, contracts}]` to preserve insertion order and
   simplify React state management.

4. **Port 5173 for production, 8000 for dev backend.** The server started by
   `subgraph-wizard --ui` listens on 5173. During development, the FastAPI
   backend runs separately on 8000; Vite (5173) proxies `/api/*` to it.

5. **shadcn/ui not used.** All UI is plain Tailwind CSS.
