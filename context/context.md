# Project Context

## What this is

**Subgraph Generator** — a visual drag-and-drop tool for building Ethereum subgraphs for
[The Graph](https://thegraph.com/) protocol without writing code by hand.

Users wire together nodes on a canvas to describe what on-chain data they want to index.
A **FastAPI** backend compiles the visual graph into **AssemblyScript** mapping files, a
`subgraph.yaml` manifest, a `schema.graphql`, and a `networks.json` — a complete, deployable
subgraph project.

**Three entry points:**

| Mode | Command | Description |
|---|---|---|
| Visual editor | `subgraph-wizard --ui` | Local web UI; drag-and-drop node canvas (primary path) |
| Interactive wizard | `subgraph-wizard` | Text Q&A flow |
| Config-driven | `subgraph-wizard --config cfg.json --generate` | Non-interactive / CI |

---

## Architecture

- **Backend:** FastAPI (`src/subgraph_wizard/server.py`) — serves the pre-built React bundle,
  exposes REST endpoints for ABI parsing, config CRUD, graph validation, and code generation.
- **Frontend:** React + React Flow (`frontend/`) — the visual canvas. Built with Vite.
  The compiled bundle is committed to `src/subgraph_wizard/static/` and served by FastAPI.
- **Graph compiler:** `generate/graph_compiler.py` — topological traversal of the node graph;
  emits AssemblyScript handler functions.
- **Validator:** `generate/validator.py` — runs on every canvas change via debounced POST to
  `/api/validate`; returns error and warning codes. The Generate button is disabled while
  `has_errors === true`.

---

## File Structure

```
subgraphGenerator/
├── src/subgraph_wizard/
│   ├── main.py                  # Entry point: routes --ui / interactive / config
│   ├── cli.py                   # argparse: --ui, --port, --no-browser, --config, --generate, --dry-run
│   ├── server.py                # FastAPI app + API routes + static file serving
│   ├── interactive_wizard.py    # Interactive Q&A flow (run_wizard())
│   ├── networks.py              # SUPPORTED_NETWORKS dict
│   ├── logging_setup.py         # Logging config (LOG_LEVEL env var)
│   ├── errors.py                # SubgraphWizardError, ValidationError, AbiFetchError
│   ├── config/
│   │   ├── model.py             # SubgraphConfig, ContractConfig, TemplateConfig dataclasses
│   │   ├── io.py                # load_config() / save_config()
│   │   └── validation.py        # Config validation rules
│   ├── abi/
│   │   ├── local.py             # Load ABI from local JSON file
│   │   ├── paste.py             # Interactive ABI paste
│   │   ├── etherscan.py         # Fetch ABI from Etherscan-compatible explorer APIs
│   │   └── utils.py             # ABI parsing, event/read-fn extraction, Solidity→GQL type mapping
│   ├── generate/
│   │   ├── orchestrator.py      # CLI generation pipeline
│   │   ├── graph_compiler.py    # Visual graph → AssemblyScript code
│   │   ├── validator.py         # Visual graph validation (errors + warnings)
│   │   ├── networks_json.py     # Write networks.json from visual config
│   │   ├── subgraph_yaml.py     # Generates subgraph.yaml (CLI and visual modes)
│   │   ├── schema.py            # Generates schema.graphql (CLI mode)
│   │   ├── mappings_auto.py     # Generates functional TypeScript handlers (CLI mode)
│   │   ├── mappings_stub.py     # Generates stub TypeScript handlers (CLI mode)
│   │   ├── package_json.py      # Generates package.json
│   │   ├── project_layout.py    # Creates directory structure
│   │   └── readme.py            # Generates README for output subgraph
│   ├── static/                  # Pre-built React bundle (committed, served by FastAPI)
│   └── utils/
│       ├── fs_utils.py
│       ├── templating.py        # Jinja2 wrapper
│       └── prompts_utils.py     # Reusable prompt helpers
├── frontend/                    # React + Vite source (contributors only)
│   ├── src/
│   │   ├── App.jsx              # Main canvas; save/load/generate/validation wiring
│   │   ├── nodes/               # ContractNode, EntityNode, AggregateEntityNode,
│   │   │                        #   MathNode, TypeCastNode, StringConcatNode,
│   │   │                        #   ConditionalNode, ContractReadNode
│   │   ├── hooks/
│   │   │   └── useValidation.js # Debounced POST /api/validate; returns issue maps
│   │   └── components/
│   │       ├── HelpPanel.jsx         # Slide-in help reference
│   │       ├── GenerateModal.jsx     # Directory-picker modal for the Generate action
│   │       ├── ValidationPanel.jsx   # Collapsible bottom-left issues list
│   │       ├── NetworksPanel.jsx     # Right-side chain address panel
│   │       └── Toolbar.jsx           # Left-side node palette
│   ├── vite.config.js           # Proxy /api → :8000 in dev; build → static/
│   └── package.json
├── templates/                   # Jinja2 templates (CLI mode)
├── tests/                       # 147 passing tests
│   ├── test_validator.py        # Visual graph validator tests
│   ├── test_server.py           # FastAPI endpoint tests
│   └── ...
├── docs/
├── context/
│   └── context.md               # This file
├── pyproject.toml
└── .env.example
```

---

## Node Types (Visual Editor)

### Contract — `contract`

Represents a smart contract. Always a data **source** — nothing is wired into it.

After the ABI is loaded, ports appear automatically.

**Output ports (always present once ABI is loaded):**

| Port | Type | Description |
|---|---|---|
| `implicit-address` | Address | `event.address` — the contract address that fired the event (runtime value) |
| `implicit-instance-address` | Address | The hardcoded deployed address from the Networks/Instances config |
| `implicit-tx-hash` | Bytes | Transaction hash of the triggering transaction |
| `implicit-block-number` | BigInt | Block number when the event was emitted |
| `implicit-block-timestamp` | BigInt | Unix timestamp of the block |
| `event-{Name}` | trigger (amber) | Fires once per occurrence of this event |
| `event-{Name}-{param}` | varies | Individual parameter value — revealed by clicking the ▶ chevron |

**Note on address vs deployed address:**
- `implicit-address` = `event.address` (runtime — the contract that emitted the event)
- `implicit-instance-address` = the hardcoded address from the Instances config (static)

---

### Entity — `entity`

A GraphQL entity. Creates **one new record per event** occurrence (append-only history).

**Ports:**

| Port | Side | Description |
|---|---|---|
| `evt` | in | Wire from a Contract event port — triggers a save |
| `field-{name}` | in | Value to store in this field. If unwired, the compiler uses the event parameter of the same name automatically. |

**Field types:** `ID`, `String`, `Bytes`, `Boolean`, `Int`, `BigInt`, `BigDecimal`, `Address`,
or any other Entity/Aggregate Entity name (entity reference / foreign key).

**ID strategy options:** `tx.hash`, `tx.hash + log index`, `event.address`, `Custom` (wire to `field-id`).

**`@derivedFrom` support:** Mark an entity-reference field as a virtual reverse relation by clicking
the link icon and entering the field name in the child entity. No input port is shown; no
AssemblyScript is emitted for it — The Graph resolves it at query time.

---

### Aggregate Entity — `aggregateEntity`

A **singleton record** updated in-place on each event. Use for running totals, cumulative balances,
or latest-state tracking.

**Trigger mechanism — checklist, not a wire:**
The node has a **Trigger Events** checklist in its header. Tick the checkbox next to each event
(from any contract on the canvas) that should fire this handler. No `evt` wire is used.
Multiple events from multiple contracts can all trigger the same aggregate node.

**Ports:**

| Port | Side | Description |
|---|---|---|
| `field-id` | in | Stable lookup key for this record (e.g. a contract address). Wire a fixed value. |
| `field-in-{name}` | in | New value to write into the field — usually a Math node result. |
| `field-out-id` | out | Exposes the stable ID as an output wire — use as a foreign key in a related history Entity. |
| `field-prev-{name}` | out | The value stored in the field BEFORE this update — feed into Math nodes to accumulate. |

**Pattern for running totals:**
`field-prev-balance` → Math(add) left; event param → Math(add) right; Math result → `field-in-balance`.

---

### Math — `math`

Binary arithmetic on two `BigInt` or `BigDecimal` values.

**Ports:** `left` (in), `right` (in), `result` (out).

**Operations:** add, subtract, multiply, divide, modulo, power.

---

### TypeCast — `typecast`

Converts a value from one Graph type to another. 7 cast modes (stored as `castIndex` 0–6):

`BigInt → Int`, `BigInt → String`, `Bytes → String`, `Bytes → Address`,
`String → Bytes`, `Address → String`, `Address → Bytes`.

**Ports:** `value` (in), `result` (out).

---

### String Concat — `strconcat`

Concatenates two `String` or `Bytes` values with an optional separator.

**Ports:** `left` (in), `right` (in), `result` (out).

---

### Conditional — `conditional`

Boolean guard. If `condition` is false, the entire handler exits early — no entity is saved.

**Ports:** `condition` (in, Boolean), `value` (in, any), `value-out` (out, any).

---

### Contract Read — `contractread`

Calls a view/pure function on a contract during an event handler to fetch extra on-chain data.

**Setup:** Select the target Contract from a dropdown, then select the function. Ports are
generated from the ABI.

**Address binding:** The node **automatically uses the instance address** configured for the
selected contract in the Networks panel. No bind-address wire is needed for cross-contract reads.

**Optional override:** Wire a dynamic `Address` value into the `address` input port to override
the auto-bound instance address.

**Ports:**

| Port | Side | Description |
|---|---|---|
| `address` | in | Optional override address — uses the configured instance address if unwired. |
| `in-{paramName}` | in | Argument for the function call. One port per ABI parameter. |
| `out-{returnName}` | out | Return value from the call. One port per ABI return value. |

---

## Key Design Decisions

### `address` ABI type → `Address` Graph type
Solidity `address` parameters now map to the `Address` Graph type (not `Bytes`).
This affects port types on Contract nodes and the type-checking logic in the validator and compiler.

### Contract Read auto-bind to instance address
`ContractReadNode` reads the selected contract's instance address from the Networks config
and binds it automatically. Users no longer need to wire `implicit-instance-address` into
a bind-address port for cross-contract calls. The optional `address` input port still exists
for dynamic address override scenarios.

### `implicit-instance-address` port on Contract
A dedicated output port (`implicit-instance-address`) on the Contract node exposes the
hardcoded deployed address from the Instances config as a wire-able value. This is distinct
from `implicit-address` (`event.address`, which is the runtime firing address).

### Aggregate Entity trigger events checklist
Aggregate Entity nodes no longer use an `evt` wire. Instead, each node has a
**Trigger Events** checklist in its UI. Checking an event from any contract on the canvas
connects that event handler to the aggregate. The compiler reads the `triggerEvents` list
on the node data to generate the correct handlers.

### `field-out-id` port on Aggregate Entity
The `id` field on an Aggregate Entity has a right-side output port (`field-out-id`) that
exposes the stable key as a wire-able output. This lets you link a history Entity's foreign-key
field to the aggregate's ID without repeating the key computation.

### `@derivedFrom` support on Entity fields
Entity fields with an entity-reference type can be marked as `@derivedFrom` by clicking
the link icon and entering the referencing field name. These fields are virtual — no input
port is shown and no AssemblyScript is emitted for them. The Graph resolves them at query time.

### BFS-based node hiding on contract collapse

When a Contract node is collapsed (click its header), the canvas hides **all** downstream nodes
reachable from that contract via a BFS traversal of the edge graph — not just entity nodes.
This includes Math, TypeCast, ContractRead, Entity, AggregateEntity, and any other node type
wired downstream of the collapsed contract.

A node is only hidden if it is **exclusively** reachable via collapsed contracts. If a node is
also reachable from an expanded contract (shared-node case), it remains visible. The set of
hidden node IDs is computed in `App.jsx` using `useMemo` every time nodes or edges change.

Expanding a contract restores all hidden nodes and edges automatically.

---

### Entity field type dropdown stale-closure bug fix
The field type dropdown in EntityNode previously suffered from a stale closure where the
handler captured an outdated copy of the fields array, causing earlier fields to be overwritten
when a later field's type was changed. This was fixed by using a functional state updater
(`setFields(prev => ...)`) so each update always operates on the latest state.

### Auto-fill strict type checking (`graph_compiler.py`)
When an entity field has no explicit wire, the compiler auto-fills it from the event parameter
with the same name. Previously, type mismatches were silently skipped (producing null fields in
the deployed subgraph). Now, any type mismatch raises a `ValueError` immediately — the generate
step fails with a diagnostic message before writing any files.

Compatibility exceptions (handled by `_types_compatible()`):
- Exact type match → compatible
- `Address` param → `Bytes` field → compatible (`Address extends Bytes` in AssemblyScript)
All other cross-type combinations are hard errors.

### Indexed reference-type parameters → `Bytes` (`abi/utils.py`)
When `extract_events` processes an ABI event parameter that is both `indexed: true` and a
reference type (array, `bytes`, `string`, `tuple`), it emits `graph_type: "Bytes"` rather than
expanding the element type. This matches graph-cli's behaviour: indexed reference types are
keccak256-hashed before being stored in log topics, so only the hash (32 bytes) is available
at indexing time. The `_is_reference_type()` helper identifies these types.

### Networks panel → compiler address lookup
The compiler (`graph_compiler.py`) builds `_network_address_by_type` from
`visual_config["networks"]` at initialisation. When resolving `implicit-instance-address`,
it falls back to this dict if the Contract node's inline address field is empty. This ensures
contracts configured via the Networks panel get the correct address without requiring users to
also fill in the inline field.

---

## FastAPI Endpoints (`server.py`)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/abi/parse` | Parse raw ABI JSON; returns events + read functions |
| `POST` | `/api/abi/fetch` | Fetch ABI from Etherscan; returns abi + events + read functions |
| `GET` | `/api/config` | Load `visual-config.json` (scaffold if missing) |
| `POST` | `/api/config` | Save `visual-config.json`; returns `{saved, path}` |
| `POST` | `/api/validate` | Validate graph; returns `{issues, has_errors}` |
| `POST` | `/api/generate` | Compile + write output files; returns `{files, dir}` |
| `GET`  | `/api/fs/browse` | List subdirectories at `?path=<path>` (defaults to home); returns `{path, parent, dirs}` |
| `POST` | `/api/fs/mkdir` | Create a directory; body `{path}`; returns `{path}` or 400/422 on error |

All endpoints accept `?dir=<path>` to override the working directory.

---

## Graph Validator (`generate/validator.py`)

**Error codes** (block generation):
- `CONTRACT_NO_NAME`, `CONTRACT_NO_ABI`
- `ENTITY_NO_NAME`, `ENTITY_NO_ID_WIRED`
- `TYPE_MISMATCH`
- `CONTRACTREAD_NO_CONTRACT`, `CONTRACTREAD_BAD_FN_INDEX`

**Warning codes** (generation continues):
- `CONTRACT_EMPTY_INSTANCE`, `DISCONNECTED_CONTRACT`, `DISCONNECTED_ENTITY`
- `ENTITY_NO_FIELDS`
- `MATH_DISCONNECTED_INPUT`, `STRCONCAT_DISCONNECTED`
- `CONDITIONAL_NO_CONDITION`
- `TYPECAST_BAD_INDEX`

---

## Solidity → Graph Type Mapping (`abi/utils.py`)

| Solidity | Graph type | Notes |
|---|---|---|
| `uint8`–`uint32` | `Int` | |
| `uint64`+ | `BigInt` | |
| `address` | `Address` | |
| `bool` | `Boolean` | |
| `string` | `String` | |
| `bytes`, `bytesN` | `Bytes` | |
| `int8`–`int32` | `Int` | |
| `int64`+ | `BigInt` | |
| `T[]`, `T[N]` (non-indexed) | `[GraphType!]` | Expanded to list notation |
| `T[]`, `T[N]` (indexed) | `Bytes` | Only the keccak256 hash is stored in the log topic — actual values are not recoverable |
| `bytes`, `string`, `tuple` (indexed) | `Bytes` | Same reason — reference types are hashed when indexed |

**Indexed reference-type rule:** When a parameter has `"indexed": true` in the ABI AND its
Solidity type is a reference type (any array, `bytes`, `string`, or `tuple`), the parser
emits `graph_type: "Bytes"` regardless of the element type. This matches what graph-cli
generates and prevents TS2322 AssemblyScript build errors.

---

## `visual-config.json` Format

```json
{
  "schema_version": 1,
  "subgraph_name": "my-subgraph",
  "networks": [
    {
      "network": "mainnet",
      "contracts": {
        "ERC20": {
          "instances": [
            { "label": "USDC", "address": "0x...", "startBlock": 6082465 }
          ]
        }
      }
    }
  ],
  "nodes": [...],
  "edges": [...]
}
```

---

## Generated Output Structure

**Visual editor mode:**
```
<output-dir>/
├── visual-config.json         ← saved graph state
├── subgraph.yaml
├── schema.graphql
├── networks.json              ← per-chain addresses
├── package.json               ← npm scripts: codegen / build / deploy
├── howto.md                   ← step-by-step deployment guide to The Graph Studio
└── src/mappings/
    └── {ContractType}.ts      ← compiled AssemblyScript
```

---

## Testing

**776 tests passing** (as of 2026-04-30).

```bash
pytest              # all tests
pytest -v
pytest tests/test_validator.py   # validator only
pytest tests/test_server.py      # server/API only
```

Notable test files:
- `test_validator.py` — covers all node types, type mismatch, aggregate trigger checklist, issue structure
- `test_server.py` — health, ABI parse/fetch, config CRUD, validate, generate endpoints

---

## Dev Setup

```bash
# Backend (port 8000)
pip install -e .
uvicorn subgraph_wizard.server:app --port 8000 --reload

# Frontend (port 5173, proxies /api → :8000)
cd frontend && npm install && npm run dev

# Build frontend for distribution
cd frontend && npm run build
# outputs to src/subgraph_wizard/static/ (committed to git)
```

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `ETHERSCAN_API_KEY` | Etherscan API key (ethereum) |
| `OPTIMISM_ETHERSCAN_API_KEY` | Optimism explorer API key |
| `ARBITRUM_ETHERSCAN_API_KEY` | Arbiscan API key |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`) |
| `DEBUG` | `1` / `true` to show full tracebacks |
| `VITE_API_PORT` | Override FastAPI port during frontend dev (default `8000`) |

---

## Git / Deployment

- Remote: `git@github.com:imimim-username/subgraphGenerator.git`
- Branch: `main`
- Push command: `git push`

---

### GenerateModal.jsx — directory picker

The **Generate** button no longer immediately generates files. Instead it opens a modal
(`frontend/src/components/GenerateModal.jsx`) with two modes:

- **Type path** (default): free-form monospace text input. Press `Enter` or click Generate.
  Press `Escape` or click the backdrop to cancel.
- **Browse…**: server-backed filesystem navigator powered by `GET /api/fs/browse`.
  Click folders to descend, use the ↑ chevron to go up, click the folder-plus icon to create
  a new subdirectory (`POST /api/fs/mkdir`) and navigate into it. The text input goes read-only
  showing the current browsed path. Click **Type path** to return to manual entry.

The modal stores the last-used directory in `genDir` state in `App.jsx` and passes it as
`initialDir` on next open. The Generate button is disabled (and styled accordingly) until a
non-empty directory is selected. All `<button>` elements inside the modal carry `type="button"`
to prevent accidental form submission if the modal is ever wrapped in a form.

---

## Recent Changes (2026-04-29)

- **Aggregate Entity redesigned:** trigger events are now configured via a checklist in the
  node UI, not via an `evt` wire. The compiler reads `triggerEvents` from node data.
- **`field-out-id` port added** on Aggregate Entity: exposes the stable ID as a wire-able output
  for use as a foreign key in related history entities.
- **Contract Read auto-bind:** ContractReadNode now automatically binds to the selected
  contract's configured instance address. The `bind-address` wire is no longer needed for
  cross-contract reads. An optional `address` override port remains for dynamic address scenarios.
- **`implicit-instance-address` port added** on Contract nodes: exposes the hardcoded deployed
  address as a wire-able output (distinct from `implicit-address` / `event.address`).
- **`address` → `Address` ABI type mapping:** Solidity `address` parameters now map to the
  `Address` Graph type instead of `Bytes`.
- **`@derivedFrom` support:** Entity fields with entity-reference types can be marked as virtual
  reverse relations via the link icon; no input port or AssemblyScript is generated for them.
- **Entity field type dropdown stale-closure bug fixed:** functional state updater pattern
  prevents earlier fields from being overwritten when a later field's type is changed.
- **Generate button now opens a directory-picker modal** (`GenerateModal.jsx`): two modes —
  free-form "Type path" input and a server-backed "Browse…" filesystem navigator.
  New API endpoints: `GET /api/fs/browse` (list dirs) and `POST /api/fs/mkdir` (create dir).
- **Generated output now includes `package.json`** (npm scripts for codegen/build/deploy) and
  **`howto.md`** (step-by-step deployment guide to The Graph Studio).
- **BFS-based node hiding on collapse:** collapsing a Contract node now hides ALL downstream
  nodes (Math, TypeCast, ContractRead, Entity, AggregateEntity, etc.) reachable only via that
  contract — not just entity nodes wired via `evt`. Shared nodes (reachable from an expanded
  contract) remain visible.
- **Test count: 147 passing.**
