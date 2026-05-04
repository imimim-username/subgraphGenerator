# Project Context

## What this is

**Subgraph Generator** — a visual drag-and-drop tool for building blockchain indexers.
Supports two output modes:

1. **The Graph** — generates AssemblyScript subgraphs (mapping files, `subgraph.yaml`,
   `schema.graphql`, `networks.json`) deployed to a Graph node.
2. **Ponder** — generates TypeScript indexers (`ponder.config.ts`, `ponder.schema.ts`,
   `src/index.ts`, `src/api/index.ts`) running as a self-hosted Node.js process.

Users wire together nodes on a canvas to describe what on-chain data they want to index.
A **FastAPI** backend compiles the visual graph into the appropriate output files.

**Three entry points:**

| Mode | Command | Description |
|---|---|---|
| Visual editor | `subgraph-wizard --ui` | Local web UI; drag-and-drop node canvas (primary path) |
| Interactive wizard | `subgraph-wizard` | Text Q&A flow (The Graph only) |
| Config-driven | `subgraph-wizard --config cfg.json --generate` | Non-interactive / CI (The Graph only) |

---

## Architecture

- **Backend:** FastAPI (`src/subgraph_wizard/server.py`) — serves the pre-built React bundle,
  exposes REST endpoints for ABI parsing, config CRUD, graph validation, and code generation.
- **Frontend:** React + React Flow (`frontend/`) — the visual canvas. Built with Vite.
  The compiled bundle is committed to `src/subgraph_wizard/static/` and served by FastAPI.
- **The Graph compiler:** `generate/graph_compiler.py` — topological traversal of the node
  graph; emits AssemblyScript handler functions.
- **Ponder compiler:** `generate/ponder_compiler.py` — same graph traversal; emits TypeScript
  `ponder.on("Contract:Event", ...)` handler functions.
- **Ponder config/schema generators:** `generate/ponder_config.py`,
  `generate/ponder_schema.py` — emit `ponder.config.ts`, `ponder.schema.ts`, and all
  Ponder boilerplate files.
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
│   │   ├── etherscan.py         # Fetch ABI + deployment block from Etherscan-compatible explorer APIs
│   │   └── utils.py             # ABI parsing, event/read-fn extraction, Solidity→GQL type mapping
│   ├── generate/
│   │   ├── orchestrator.py      # CLI generation pipeline (The Graph)
│   │   ├── graph_compiler.py    # Visual graph → AssemblyScript code (The Graph)
│   │   ├── validator.py         # Visual graph validation (errors + warnings)
│   │   ├── networks_json.py     # Write networks.json from visual config
│   │   ├── subgraph_yaml.py     # Generates subgraph.yaml (CLI and visual modes)
│   │   ├── schema.py            # Generates schema.graphql (CLI mode)
│   │   ├── mappings_auto.py     # Generates functional TypeScript handlers (CLI mode)
│   │   ├── mappings_stub.py     # Generates stub TypeScript handlers (CLI mode)
│   │   ├── package_json.py      # Generates package.json
│   │   ├── project_layout.py    # Creates directory structure
│   │   ├── readme.py            # Generates README for output subgraph
│   │   ├── ponder_config.py     # Ponder: ponder.config.ts + all boilerplate (PONDER_HOWTO.md etc.)
│   │   ├── ponder_schema.py     # Ponder: ponder.schema.ts (onchainTable definitions)
│   │   └── ponder_compiler.py   # Ponder: src/index.ts event handler functions
│   ├── static/                  # Pre-built React bundle (committed, served by FastAPI)
│   └── utils/
│       ├── fs_utils.py
│       ├── templating.py        # Jinja2 wrapper
│       └── prompts_utils.py     # Reusable prompt helpers
├── frontend/                    # React + Vite source (contributors only)
│   ├── src/
│   │   ├── App.jsx              # Main canvas; save/load/generate/validation wiring; ponderSettings state
│   │   ├── nodes/               # ContractNode, EntityNode, AggregateEntityNode,
│   │   │                        #   MathNode, TypeCastNode, StringConcatNode,
│   │   │                        #   ConditionalNode, ContractReadNode
│   │   ├── hooks/
│   │   │   └── useValidation.js # Debounced POST /api/validate; returns issue maps
│   │   └── components/
│   │       ├── HelpPanel.jsx         # Slide-in help reference (covers both Graph and Ponder modes)
│   │       ├── GenerateModal.jsx     # Directory-picker modal; Ponder Settings section when in Ponder mode
│   │       ├── ValidationPanel.jsx   # Collapsible bottom-left issues list
│   │       ├── NetworksPanel.jsx     # Right-side chain address panel; endBlock + advanced options
│   │       └── Toolbar.jsx           # Left-side node palette
│   ├── vite.config.js           # Proxy /api → :8000 in dev; build → static/
│   └── package.json
├── templates/                   # Jinja2 templates (CLI mode)
├── tests/                       # 1119+ passing tests
│   ├── test_validator.py        # Visual graph validator tests
│   ├── test_server.py           # FastAPI endpoint tests
│   ├── test_ponder_config.py    # ponder_config.py unit + integration tests
│   ├── test_ponder_compiler.py  # ponder_compiler.py unit tests
│   ├── test_ponder_schema.py    # ponder_schema.py unit tests
│   ├── test_full_generation_ponder.py  # End-to-end Ponder generation tests
│   ├── test_etherscan_deployment_block.py  # Etherscan startBlock detection tests
│   └── ...
├── docs/
├── context/
│   └── context.md               # This file
├── pyproject.toml
└── .env.example
```

---

## Output Modes

### The Graph output

```
<output-dir>/
├── subgraph.yaml
├── schema.graphql
├── networks.json              ← per-chain addresses + start blocks
├── package.json               ← npm scripts: codegen / build / deploy
├── howto.md                   ← step-by-step deployment guide to The Graph Studio
└── src/mappings/
    └── {ContractType}.ts      ← compiled AssemblyScript
```

### Ponder output

```
<output-dir>/
├── ponder.config.ts           ← chains{}, contracts{} with addresses + start blocks
├── ponder.schema.ts           ← onchainTable definitions (one per entity node)
├── ponder-env.d.ts            ← Ponder environment typings (boilerplate)
├── tsconfig.json              ← TypeScript project config
├── package.json               ← pnpm dev / start / codegen scripts
├── .env.example               ← RPC URL placeholders (one per chain)
├── PONDER_HOWTO.md            ← step-by-step guide tailored to the canvas settings
└── src/
    ├── api/
    │   └── index.ts           ← Hono app; mounts /graphql and / (GraphiQL)
    └── index.ts               ← ponder.on("Contract:Event", ...) handler functions
```

---

## Ponder-Specific Design Notes

### GraphQL endpoint (Ponder ≥ 0.8)

Since Ponder 0.8 the `/graphql` endpoint is **not** served automatically. The generated
`src/api/index.ts` uses the Hono framework and explicitly mounts `graphql({ db, schema })`
(imported from `"ponder"`) at both `/graphql` (API) and `/` (GraphiQL playground).

```ts
import { db } from "ponder:api";
import schema from "ponder:schema";
import { graphql } from "ponder";
import { Hono } from "hono";

const app = new Hono();
app.use("/graphql", graphql({ db, schema }));
app.use("/", graphql({ db, schema }));
export default app;
```

### Auto `chain` column

`ponder_schema.py` appends a `chain: t.text().notNull()` column after `id` in every
`onchainTable`. `ponder_compiler.py` then sets `chain: context.chain.name` on every insert,
so data from different networks is distinguishable without any extra canvas wiring.

> **Note:** Ponder 0.8 renamed `context.network` → `context.chain`. All generated code uses
> `context.chain.name`.

### Suffix-retry inserts

Ponder rejects duplicate primary keys. The compiler wraps every insert in a retry loop:

```ts
let __baseId = event.transaction.hash;
let __id = __baseId;
let __suffix = 0;
let __inserted = false;
while (!__inserted) {
  try {
    await context.db.insert(myTable).values({ id: __id, chain: context.chain.name, ... });
    __inserted = true;
  } catch {
    __suffix++;
    __id = `${__baseId}-${__suffix}`;
  }
}
```

### Multi-chain, one indexer

All networks in the Networks panel are indexed concurrently inside a single Ponder process
stored in the same database. The `chain` column separates data from different networks.

### startBlock auto-detection

When a contract instance has `startBlock == 0` and a real (non-zero) address, `ponder_config.py`
calls `get_contract_deployment_block(slug, addr)` from `abi/etherscan.py` to auto-detect the
deployment block. Requires `ETHERSCAN_API_KEY` in the environment; silently skips if absent.

Mock target for tests: `"subgraph_wizard.abi.etherscan.get_contract_deployment_block"`
(lazy import — patch at source, not at the `ponder_config` namespace).

### Ponder settings (`ponder_settings` in visual-config.json)

| Field | Type | Default | Description |
|---|---|---|---|
| `database` | `"pglite"` \| `"postgres"` | `"pglite"` | Database backend. `postgres` emits a `database: { kind: "postgres", connectionString: process.env.DATABASE_URL }` block. |
| `dbUrl` | `string` | `""` | Informational only — runtime reads `DATABASE_URL` from env. |
| `ordering` | `"multichain"` \| `"omnichain"` \| `"experimental_isolated"` | `"multichain"` | Ponder event ordering mode. Default (`multichain`) is omitted from config. |

### Per-contract Ponder options (stored on Contract node data)

| Field | Description |
|---|---|
| `endBlock` | Optional stop block. Written to `ponder.config.ts` when non-empty. |
| `includeCallTraces` | Emit `includeCallTraces: true` in contract config. |
| `includeTransactionReceipts` | Emit `includeTransactionReceipts: true` in contract config. |
| `hasSetupHandler` | Generate a `ponder.on("ContractName:setup", ...)` handler stub. Adds a `setup` trigger port on the node. |

### Per-network advanced options (stored on network entries)

| Field | Description |
|---|---|
| `pollingInterval` | RPC polling interval (ms). Written to chain config. |
| `maxBlockRange` | Max block range for `eth_getLogs`. Written to chain config. |

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

**Ponder Options (collapsible section on node):**
- `endBlock` input
- `includeTransactionReceipts` checkbox
- `includeCallTraces` checkbox
- `hasSetupHandler` checkbox — adds `event-setup` trigger port

---

### Entity — `entity`

A GraphQL entity. Creates **one new record per event** occurrence (append-only history).

In Ponder mode: becomes an `onchainTable` with an auto-added `chain` column.

**Ports:**

| Port | Side | Description |
|---|---|---|
| `evt` | in | Wire from a Contract event port — triggers a save |
| `field-{name}` | in | Value to store in this field. If unwired, auto-fills from matching event parameter name. |

**Field types:** `ID`, `String`, `Bytes`, `Boolean`, `Int`, `BigInt`, `BigDecimal`, `Address`,
or any other Entity/Aggregate Entity name (entity reference / foreign key).

**ID strategy options:** `tx.hash`, `tx.hash + log index`, `event.address`, `Custom` (wire to `field-id`).

**`@derivedFrom` support (The Graph only):** Mark an entity-reference field as a virtual
reverse relation. No input port shown; no code emitted — The Graph resolves at query time.

---

### Aggregate Entity — `aggregateEntity`

A **singleton record** updated in-place on each event. Use for running totals, cumulative
balances, or latest-state tracking.

**Trigger mechanism — checklist, not a wire:**
The node has a **Trigger Events** checklist in its header. Tick the checkbox next to each
event that should fire this handler. No `evt` wire is used.

**Ports:**

| Port | Side | Description |
|---|---|---|
| `field-id` | in | Stable lookup key for this record (e.g. a contract address). |
| `field-in-{name}` | in | New value to write into the field — usually a Math node result. Only rendered when field has a non-empty name. |
| `field-out-id` | out | Exposes the stable ID as an output wire — use as a foreign key in a related Entity. |
| `field-prev-{name}` | out | Value stored before this update — feed into Math nodes to accumulate. Only rendered when field has a non-empty name. |

**Important:** Port handle IDs are derived only from `field.name` — never a numeric fallback.
Fields without a name render no handle. This prevents stale wire handles after renaming.

---

### Math — `math`

Binary arithmetic on two `BigInt` or `BigDecimal` values.

**Ports:** `left` (in), `right` (in), `result` (out).

**Operations:** add, subtract, multiply, divide, modulo, power.

---

### TypeCast — `typecast`

Converts a value from one type to another. 7 cast modes (stored as `castIndex` 0–6):

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

**Address binding:** Automatically uses the instance address configured for the selected
contract in the Networks panel. No bind-address wire needed for cross-contract reads.

**Optional override:** Wire a dynamic `Address` value into the `address` input port.

**Ports:**

| Port | Side | Description |
|---|---|---|
| `address` | in | Optional override address — uses the configured instance address if unwired. |
| `in-{paramName}` | in | Argument for the function call. One port per ABI parameter. |
| `out-{returnName}` | out | Return value from the call. One port per ABI return value. |

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
| `POST` | `/api/generate` | Compile + write output files; returns `{files, dir}` — respects `output_mode` field |
| `GET`  | `/api/fs/browse` | List subdirectories at `?path=<path>` (defaults to home) |
| `POST` | `/api/fs/mkdir` | Create a directory; body `{path}` |

The `POST /api/generate` body includes `output_mode: "graph" | "ponder"`. When `"ponder"`,
the server calls `ponder_config.py`, `ponder_schema.py`, and `ponder_compiler.py` instead of
the Graph pipeline.

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
- `WIRE_UNKNOWN_PORT` (wire targets a port that no longer exists — stale after canvas edits)

---

## Solidity → Graph / Ponder Type Mapping (`abi/utils.py`)

| Solidity | Graph type | Ponder type |
|---|---|---|
| `uint8`–`uint32` | `Int` | `t.integer()` |
| `uint64`+ | `BigInt` | `t.bigint()` |
| `address` | `Address` | `t.hex()` |
| `bool` | `Boolean` | `t.boolean()` |
| `string` | `String` | `t.text()` |
| `bytes`, `bytesN` | `Bytes` | `t.hex()` |
| `int8`–`int32` | `Int` | `t.integer()` |
| `int64`+ | `BigInt` | `t.bigint()` |
| `T[]`, `T[N]` (non-indexed) | `[GraphType!]` | `t.text()` (JSON) |
| `T[]`, `T[N]` (indexed) | `Bytes` | `t.hex()` |
| `BigDecimal` | `BigDecimal` | `t.text()` (stored as string) |

**Indexed reference-type rule:** When a parameter has `"indexed": true` AND its Solidity
type is a reference type (any array, `bytes`, `string`, or `tuple`), the parser emits
`graph_type: "Bytes"` — only the keccak256 hash is stored in the log topic.

---

## `visual-config.json` Format

```json
{
  "schema_version": 1,
  "subgraph_name": "my-project",
  "output_mode": "ponder",
  "ponder_settings": {
    "database": "pglite",
    "dbUrl": "",
    "ordering": "multichain"
  },
  "networks": [
    {
      "network": "mainnet",
      "contracts": {
        "ERC20": {
          "instances": [
            {
              "label": "USDC",
              "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
              "startBlock": 6082465,
              "endBlock": ""
            }
          ],
          "pollingInterval": null,
          "maxBlockRange": null
        }
      }
    }
  ],
  "nodes": [...],
  "edges": [...]
}
```

---

## Key Design Decisions

### `address` ABI type → `Address` Graph type
Solidity `address` parameters map to the `Address` Graph type (not `Bytes`).

### Contract Read auto-bind to instance address
`ContractReadNode` reads the selected contract's instance address from the Networks config
and binds it automatically. The optional `address` input port still exists for dynamic
address override scenarios.

### `implicit-instance-address` port on Contract
A dedicated output port exposing the hardcoded deployed address as a wire-able value.
Distinct from `implicit-address` (`event.address`, the runtime firing address).

### Aggregate Entity trigger events checklist
Aggregate Entity nodes no longer use an `evt` wire. Each node has a **Trigger Events**
checklist in its UI. The compiler reads the `triggerEvents` list on node data to generate
the correct handlers.

### Aggregate Entity port handles — no numeric fallback
Handle IDs (`field-in-{name}`, `field-prev-{name}`) are only rendered when `field.name` is
non-empty. Using a numeric-index fallback (`field.name || idx`) caused stale wire handles
after fields were renamed. The fix ensures users must name a field before wiring it.

### `field-out-id` port on Aggregate Entity
Exposes the stable key as a wire-able output for linking history Entity foreign-key fields.

### `@derivedFrom` support on Entity fields (The Graph only)
Entity fields with entity-reference types can be marked as `@derivedFrom` via the link icon.
No input port shown; no code emitted. The Graph resolves them at query time.

### BFS-based node hiding on contract collapse
When a Contract node is collapsed, the canvas hides **all** downstream nodes reachable from
that contract via BFS — not just entity nodes. Nodes reachable from an expanded contract
remain visible.

### Auto-fill strict type checking (`graph_compiler.py`)
When an entity field has no explicit wire, the compiler auto-fills from the matching event
parameter. Type mismatches raise a `ValueError` immediately before writing any files.

### Indexed reference-type parameters → `Bytes` (`abi/utils.py`)
Indexed reference types (arrays, `bytes`, `string`, `tuple`) emit `graph_type: "Bytes"`.
Matches graph-cli's behaviour: only the keccak256 hash is stored in log topics.

---

## Testing

**1119+ tests passing.**

```bash
pytest              # all tests
pytest -v
pytest tests/test_ponder_config.py   # Ponder config + boilerplate + API index + startBlock
pytest tests/test_ponder_compiler.py # Ponder handler compiler
pytest tests/test_ponder_schema.py   # Ponder schema generator
pytest tests/test_full_generation_ponder.py  # End-to-end Ponder generation
pytest tests/test_validator.py       # Visual graph validator
pytest tests/test_server.py          # FastAPI endpoints
```

Notable test files:
- `test_ponder_config.py` — `render_ponder_config`, `render_ponder_api_index`,
  `TestAutoChainColumn`, `TestStartBlockEtherscanIntegration`
- `test_ponder_compiler.py` — `TestAutoChainField`, suffix-retry, setup handlers
- `test_validator.py` — all node types, type mismatch, aggregate trigger checklist
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
| `ETHERSCAN_API_KEY` | Etherscan API key (ethereum mainnet) — also used for startBlock auto-detection |
| `OPTIMISM_ETHERSCAN_API_KEY` | Optimism explorer API key |
| `ARBITRUM_ETHERSCAN_API_KEY` | Arbiscan API key |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`) |
| `DEBUG` | `1` / `true` to show full tracebacks |
| `VITE_API_PORT` | Override FastAPI port during frontend dev (default `8000`) |
| `PONDER_RPC_URL_{chainId}` | RPC endpoint for Ponder (set in `.env.local` in the generated project) |
| `DATABASE_URL` | PostgreSQL connection string (Ponder production mode) |

---

## Git / Deployment

- Remote: `git@github.com:imimim-username/subgraphGenerator.git`
- Active branch: `frokfixes` (bug-fix + UI polish; not yet merged to `main`)
- Push command: `git push origin frokfixes`

---

## GenerateModal.jsx — directory picker + Ponder settings

The **Generate** button opens a modal (`frontend/src/components/GenerateModal.jsx`) with:

- **Type path** (default): free-form monospace text input. Press `Enter` or click Generate.
- **Browse…**: server-backed filesystem navigator (`GET /api/fs/browse`, `POST /api/fs/mkdir`).
- **Ponder Settings** section (shown only in Ponder mode):
  - Database: radio `PGlite` / `PostgreSQL`; PostgreSQL shows a connection string input.
  - Ordering: select `multichain` / `omnichain` / `experimental_isolated`.

`ponderSettings` state lives in `App.jsx` and is persisted in `visual-config.json` as
`ponder_settings`. It is passed into `buildPayload()` so the server receives it on generate.

---

## Known Design Limitations / Future Work

### Conditional + ContractRead = unconditional RPC call

**Severity:** Low — only hits specific canvas topologies.

When a `Conditional` node gates a `ContractRead`, the ponder compiler's preamble approach
means the `readContract` call fires **before** the ternary guard. If the condition is false
but the read arguments are invalid for that branch (e.g. they depend on event params that
only make sense when the condition is true), the handler crashes.

**Example:** Conditional checks `event.args.amount > 0`, ContractRead uses `event.args.token`
as an argument — but `token` is the zero-address when `amount == 0`, causing an RPC revert.

**Alternatives considered** (both have downsides):
- Inline everything inside the ternary — complex codegen, hard to read output
- Wrap reads in `try/catch` — silently swallows real errors

Not a simple fix. Architectural tradeoff to revisit if user demand warrants it.

---

## Recent Changes (2026-05-03)

### Bug fixes (frok review round 2)

**Bug 1 — `implicit-instance-address` resolved to wrong value in Ponder**

`_event_param_expr_ts` was incorrectly normalising `implicit-instance-address` → `implicit-address`,
causing it to emit `event.log.address` (the runtime firing address) instead of the statically
configured deployment address from the Networks panel. Fixed in `ponder_compiler.py`:

- Removed the wrong normalisation line.
- `_resolve_value_ts` now looks up the configured address from node data / instances / network
  address map and returns it as a typed string literal (`"0x..." as \`0x${string}\``).
- In setup handlers (no event param) both `implicit-address` and `implicit-instance-address`
  map to the loop variable `__address` (unchanged — correct for that context).
- Falls back to `event.log.address` with a warning log if no address is configured.

**Bug 2 — `_is_reachable_from_event` non-recursive in `graph_compiler.py`**

The Graph compiler's `_is_reachable_from_event` only checked one level of indirection, so a
Math node fed by a wrong-event port appeared reachable when it wasn't. Fixed by rewriting as a
recursive DFS with a visited-set guard (mirrors the fix already applied to `ponder_compiler.py`
in round 1). Added `_transform_input_handles()` helper method to both compilers.

**Bug 3 — Aggregate upsert double-resolution comment**

`_compile_aggregate_upsert` calls `_resolve_value_ts` twice per field (first pass emits
`const` declarations, second pass returns the expression). Added clarifying comment so future
readers don't mistake the second pass for a bug.

**Bug 4 — Entity insert preamble double-resolution comment**

Same pattern as Bug 3 in `_compile_entity_insert`. Added the same clarifying comment.

**Bug 5 — `index()` export from `"ponder"` verified**

Concern that `index()` might not be exported from the Ponder main entry. Confirmed via web
search and Uniswap's The Compact indexer:
`import { index, onchainTable, primaryKey, relations } from "ponder"`. No code change needed.

**Bug 6 — `.onConflictDoNothing()` extra leading spaces**

In `ponder_compiler.py`, the `.onConflictDoNothing()` and `.onConflictDoUpdate(...)` calls had
two extra leading spaces vs the `await` line above. Removed the extra indent.

### UI fixes

**Contract navigator in Toolbar**

The left toolbar now lists all Contract nodes on the canvas (below a "Contracts" section
divider) with a MapPin icon. Clicking a contract name zooms the canvas to that node
(`reactFlowInstance.setCenter` + `duration: 400`).

The toolbar container was given `maxHeight: calc(100vh - 80px)` and `overflowY: auto` so the
Contracts list (which appears last) is always accessible by scrolling rather than overflowing
off-screen.

**ValidationPanel offset**

`ValidationPanel` was positioned at `left: 16`, overlapping the React Flow Controls (zoom
buttons) which are also at the bottom-left. Changed to `left: 56` to clear the Controls width.

**React Flow Controls high-contrast styling**

Overrode `.react-flow__controls-button` CSS (with `!important` to beat the xyflow stylesheet)
so zoom buttons show **white icons on a near-black background** with a visible slate border
and a blue hover state. Previously the icons were nearly invisible.

---

## Recent Changes (2026-05-01)

### Ponder output mode (major feature)

Complete Ponder indexer generation from the visual canvas:

- **`ponder_config.py`** — `render_ponder_config` (createConfig with chains + contracts),
  `render_ponder_api_index` (Hono app mounting /graphql — required since Ponder 0.8),
  `render_ponder_howto` (tailored PONDER_HOWTO.md), and all boilerplate renderers.
- **`ponder_schema.py`** — converts entity/aggregate nodes to `onchainTable` definitions;
  auto-injects `chain: t.text().notNull()` after `id` in every table.
- **`ponder_compiler.py`** — emits `ponder.on(...)` handlers; sets `chain: context.chain.name`
  on every insert; suffix-retry loop for duplicate IDs; setup handler stubs.
- **`server.py`** — `VisualConfig` Pydantic model updated; `_generate_ponder` function routes
  to all three Ponder generators; `output_mode` field added to generate payload.
- **Frontend** — output mode toggle in toolbar; `ponderSettings` state in App.jsx; Ponder
  Settings section in GenerateModal; endBlock + advanced options in NetworksPanel; Ponder
  Options section + setup handler port on ContractNode.

### Etherscan startBlock auto-detection (Ponder)

`ponder_config.py` calls `get_contract_deployment_block(slug, addr)` when `startBlock == 0`
and a real address is present. 7 integration tests in `test_ponder_config.py` cover this path.
Patch target for tests: `"subgraph_wizard.abi.etherscan.get_contract_deployment_block"`.

### Auto `chain` field (Ponder)

- `ponder_schema.py`: `chain: t.text().notNull()` after `id` in every `onchainTable`.
- `ponder_compiler.py`: `chain: context.chain.name` in every insert + aggregate upsert.
- `context.chain.name` (not `context.network.name` — renamed in Ponder 0.8).

### /graphql endpoint fix (Ponder 0.8)

`render_ponder_api_index` generates `src/api/index.ts` that explicitly mounts
`graphql({ db, schema })` at `/graphql` and `/`. Without this, the endpoint returns 404
(breaking change in Ponder 0.8).

### Aggregate Entity port handle fix

`AggregateEntityNode.jsx` no longer uses numeric index as fallback for handle IDs.
Fields without a name render no port handle, preventing stale wire handles in the visual config.

### Documentation update

- `README.md`: Ponder output mode section, files table, behaviour callouts.
- `docs/user-guide.md`: Ponder quick-start section.
- `docs/config-format.md`: `ponder_settings`, per-contract and per-network Ponder options.
- `docs/architecture.md`: updated layout; section 4.5a Ponder Generation Pipeline.
- `HelpPanel.jsx`: output mode toggle docs; separate file tables for both modes.
