
# Subgraph Generator

A visual drag-and-drop tool for building blockchain indexers — targeting either
[The Graph](https://thegraph.com/) (AssemblyScript subgraphs) or
[Ponder](https://ponder.sh/) (TypeScript indexers).

Wire together nodes on a canvas to describe what on-chain data you want to index, choose an
output mode, then click **Generate** — the tool writes all the necessary source files
automatically.

---

## Quick start

```bash
# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -e .
subgraph-wizard --ui      # opens http://localhost:5173
```

The canvas opens in your browser. From there:

1. Drop a **Contract** node → upload or paste its ABI JSON (or fetch from Etherscan).
2. Drop an **Entity** node → wire an event output port (amber) to the entity's `evt` input port.
   Fields populate automatically from the event's parameters.
3. Open the **Networks** panel → add the deployed contract address and start block.
4. Choose an **output mode** with the toggle in the toolbar: **The Graph** or **Ponder**.
5. Type a project name and click **Generate**. A directory-picker modal opens — choose where
   to write the files (type a path or browse the server filesystem). Click **Generate** in
   the modal to confirm.

The output files are written to the chosen directory. See the generated `howto.md` /
`PONDER_HOWTO.md` for the full deployment walkthrough.

**CLI flags:**

```bash
subgraph-wizard --ui                # default port 5173
subgraph-wizard --ui --port 8080   # custom port
subgraph-wizard --ui --no-browser  # headless / server mode
```

---

## Node types

### Contract
Represents a deployed smart contract. Upload or paste its ABI JSON. Output ports appear
automatically — one amber trigger port per event, plus implicit ports for the block context.

| Port | Description |
|---|---|
| `implicit-address` | `event.address` — the contract address at event-fire time (runtime) |
| `implicit-instance-address` | The hardcoded deployed address from the Networks config |
| `implicit-tx-hash` | Transaction hash |
| `implicit-block-number` | Block number |
| `implicit-block-timestamp` | Unix timestamp |
| `event-{Name}` | Amber trigger port — wire to an Entity `evt` port |
| `event-{Name}-{param}` | Individual event parameter — click the ▶ chevron to reveal |
| `event-setup` | **(Ponder only)** Setup trigger port — appears when **setup handler** is enabled in Ponder Options |

**Ponder Options** (expandable section at the bottom of a Contract node):

| Option | Description |
|---|---|
| `includeTransactionReceipts` | Attach full transaction receipt to every event handler (`event.transaction.receipt`) |
| `includeCallTraces` | Enable call-trace ingestion for this contract (`ponder.on("ContractName:functionName()", ...)`) |
| **setup handler** | Emit a `ponder.on("ContractName:setup", ...)` handler that runs once per chain at startup. Exposes an `event-setup` port — wire Entity nodes to it to initialise records on startup. The generated handler wraps all logic in `try/catch` so a failed `readContract` on one chain does not crash the entire indexer. |

### Entity
Creates one new record per event occurrence — good for transaction history. Wire a Contract
event port to the `evt` input, add fields, choose an ID strategy. Field types include all
GraphQL primitives (`BigInt`, `String`, `Bytes`, `Address`, etc.) and references to other
entity types. Mark an entity-reference field as `@derivedFrom` to create a virtual reverse
relation (no data stored, resolved at query time by The Graph).

### Aggregate Entity
A singleton record updated in-place — good for running totals and current state.

**How to connect events:** use the **Trigger Events** checklist inside the node header.
Tick each event (from any contract on the canvas) that should fire this aggregate's handler.
No `evt` wire is used.

| Port | Description |
|---|---|
| `field-id` (in) | Stable lookup key — wire a fixed address or other stable value |
| `field-in-{name}` (in) | New value to write — usually a Math node result |
| `field-out-id` (out) | Exposes the stable ID for use as a foreign key in a history Entity |
| `field-prev-{name}` (out) | Previous value before this update — feed into Math nodes |

### Math
Performs a single arithmetic operation (`+`, `-`, `×`, `÷`, `%`, `^`) on two `BigInt` or
`BigDecimal` inputs and outputs the result. Both inputs must be wired.

### TypeCast
Converts between Graph types. Available casts: `BigInt → Int`, `BigInt → String`,
`Bytes → String`, `Bytes → Address`, `String → Bytes`, `Address → String`, `Address → Bytes`.

### String Concat
Joins two `String` or `Bytes` values with an optional separator. Useful for building
composite entity IDs (e.g. `poolAddress-userAddress`).

### Conditional
Boolean guard. If the `condition` input is false, the entire handler exits early — nothing
downstream is saved or executed.

### Contract Read
Calls a view/pure function on a contract during an event handler to fetch data that wasn't
in the event itself (e.g. `balanceOf` after a Transfer).

Select the target contract and function from dropdowns — ports appear from the ABI.
The node **automatically uses the configured instance address** for the selected contract;
no address wire is needed. To call the function at a dynamic address, wire it into the
optional `address` override input port.

---

## Wiring rules

- Draw wires from output ports (right side) to input ports (left side).
- A red animated wire indicates a type mismatch — insert a TypeCast node to fix it.
- Unwired Entity field ports are filled automatically from the event parameter of the same name.
- The Generate button is disabled while validation errors (red outlines) exist. Warnings
  (amber outlines) are advisory and don't block generation.
- Delete a wire or node by selecting it and pressing `Delete` / `Backspace`.

---

## Networks panel

Open with the **Networks** button. Add one entry per deployment target (e.g. mainnet, Arbitrum).
For each network, set the deployed address, start block, and optionally end block for every
Contract node. You can add multiple **instances** of the same contract type (useful for factory
patterns). Click **Detect** next to a start block field to auto-populate it from the contract's
deployment transaction.

**Instance columns:**

| Column | Description |
|---|---|
| Label | Human-readable name for this deployment instance |
| Address | Deployed contract address |
| Start block | Block at which indexing starts (inclusive) |
| End block | **(Ponder only)** Stop indexing at this block |

**Advanced per-chain settings** (expandable "Advanced" section per network):

| Setting | Description |
|---|---|
| `pollingInterval` (ms) | How often Ponder polls the RPC for new blocks (default: 1 000 ms) |
| `ethGetLogsBlockRange` | Maximum block range per `eth_getLogs` batch (default: chain-dependent) |

`networks.json` is written alongside the other output files so you can deploy to each network
by name with `graph deploy`.

---

## Output mode

Switch between two indexing targets using the **Output mode** toggle in the toolbar:

| Mode | Runtime | Language | Notes |
|---|---|---|---|
| **The Graph** | Hosted/decentralised Graph node | AssemblyScript | Classic subgraph — `subgraph.yaml`, `schema.graphql`, AS mappings |
| **Ponder** | Self-hosted Node.js process | TypeScript | Multi-chain, real-time GraphQL API out of the box |

The same canvas works for both modes — switch at any time.

---

## Generate

Click **Generate** in the toolbar to open the directory-picker modal. The modal has two modes:

| Mode | How it works |
|---|---|
| **Type path** (default) | Free-form monospace text input. Type or paste any absolute path. Press `Enter` or click Generate to confirm. Press `Escape` or click outside to cancel. |
| **Browse…** | Server-backed filesystem navigator. Click folders to descend into them; use the ↑ button to go up; click the folder-plus icon to create a new subdirectory. Click **Type path** to return to manual entry. |

### The Graph output files

| File | Description |
|---|---|
| `subgraph.yaml` | Subgraph manifest |
| `schema.graphql` | GraphQL entity schema |
| `networks.json` | Per-chain deployed addresses and start blocks |
| `src/mappings/{Contract}.ts` | Compiled AssemblyScript handlers |
| `package.json` | npm scripts: `codegen`, `build`, `deploy` |
| `howto.md` | Step-by-step deployment guide to The Graph Studio |

### Ponder output files

| File | Description |
|---|---|
| `ponder.config.ts` | Chain RPC config, contract addresses, start blocks |
| `ponder.schema.ts` | Typed database schema (one `onchainTable` per entity) |
| `src/index.ts` | TypeScript event handler functions |
| `src/api/index.ts` | Hono HTTP app; mounts `/graphql` and `/` GraphQL endpoints |
| `ponder-env.d.ts` | Auto-generated Ponder environment typings |
| `tsconfig.json` | TypeScript project config |
| `package.json` | `pnpm dev`, `pnpm start`, `pnpm codegen` scripts |
| `.env.example` | RPC URL placeholders (one per chain) |
| `PONDER_HOWTO.md` | Step-by-step guide to running and deploying the indexer |

#### Ponder-specific behaviour

- **Multi-chain, one indexer.** Every network in the Networks panel is indexed simultaneously
  in a single Ponder process.
- **Auto `chain` field.** A `chain: text().notNull()` column is automatically added to every
  entity table. Every insert sets it to `context.chain.name` so you can filter data by chain.
- **Suffix-retry inserts.** Ponder rejects duplicate primary keys. The generated handlers retry
  with a `-1`, `-2`, … suffix when the ID already exists so no event is silently dropped.
- **GraphQL at `/graphql`.** Since Ponder 0.8 the GraphQL API must be explicitly mounted.
  The generated `src/api/index.ts` mounts `graphql({ db, schema })` at both `/graphql` and
  `/` so both the API and the GraphiQL playground are accessible.
- **Database.** Defaults to PGlite (zero-config, embedded). Switch to PostgreSQL in the
  Generate modal (Ponder Settings section) or edit `ponder.config.ts` directly.
- **Ordering.** Controls multi-chain event ordering strategy. Options: `omnichain` (default —
  globally ordered), `multichain` (per-chain ordering, higher throughput), or
  `experimental_isolated` (fully isolated chains). Set in the Generate modal.
- **Setup handler resilience.** When a contract node has **setup handler** enabled, the
  generated handler wraps all logic in `try { ... } catch (err) { console.warn(...) }`.
  This prevents a failed `readContract` call on one chain (e.g. a function not implemented
  at that chain's address) from crashing the entire Ponder indexer.
- **Stale ABI cleanup.** Each Generate run auto-deletes `abis/*.ts` files for contracts that
  no longer exist on the canvas, keeping the output directory in sync.

#### Ponder Settings (Generate modal)

| Setting | Options | Description |
|---|---|---|
| Database | **PGlite** (default) / PostgreSQL | PGlite is embedded and zero-config. PostgreSQL requires a connection string (stored in `DATABASE_URL`). |
| Ordering | **omnichain** (default) / multichain / experimental_isolated | Controls how events from multiple chains are interleaved during indexing. |

The Generate button is disabled while validation errors (red outlines) exist.

---

## Canvas tools

Two utility buttons sit at the bottom of the Toolbar panel:

| Button | Description |
|---|---|
| **Auto Layout** | Runs a Dagre left-to-right layout pass over all visible nodes. Useful after adding many nodes manually. |
| **Clean Up** | Removes orphan nodes — Entity, Aggregate, Transform (Math / TypeCast / StrConcat / Conditional), and Contract Read nodes that are not connected (directly or transitively) to any Contract node. Reports the number of nodes removed. Cannot be undone; save to the Library first if needed. |

---

## Canvas Library

Open with the **Library** button. Save, load, export (`.json`), and import canvas states.
Use this to manage multiple subgraph designs or share a configuration with a team member.

---

## Example: TVL with history (Alchemix pattern)

**Goal:** maintain a single running TVL balance, and save one history row per event that
links back to the TVL record.

**TVL aggregate:**

1. Add Aggregate Entity → name `AlchemistTVL` → add field `netBalance` (BigInt).
2. Add field `activity`, type `AlchemistTVLHistory`. Click the link icon → enter `tvl`
   (creates `@derivedFrom(field: "tvl")`).
3. In the **Trigger Events** checklist, tick `Deposit`.
4. Wire `implicit-address` → `field-id`.
5. Add Math (add) → wire `field-prev-netBalance` → left, `event-Deposit-amount` → right.
6. Wire Math result → `field-in-netBalance`.

**History entity:**

1. Add Entity → name `AlchemistTVLHistory`.
2. Add field `tvl`, type `AlchemistTVL` (real foreign key — do NOT click the link icon).
3. Add field `netBalance` (BigInt).
4. Wire `event-Deposit` (amber) → `evt`.
5. Set ID strategy to `tx.hash + log index`.
6. Wire `AlchemistTVL field-out-id` → `field-tvl`.
7. Wire `event-Deposit-amount` → `field-netBalance`.

After generating, query both the TVL and its history in one GraphQL call:

```graphql
{
  alchemistTVL(id: "0x...") {
    netBalance
    activity { netBalance }
  }
}
```

---

## API endpoints

The FastAPI backend exposes these endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/abi/parse` | Parse raw ABI JSON |
| `POST` | `/api/abi/fetch` | Fetch ABI from Etherscan |
| `GET` | `/api/config` | Load `visual-config.json` |
| `POST` | `/api/config` | Save `visual-config.json` |
| `POST` | `/api/validate` | Validate graph; returns `{issues, has_errors}` |
| `POST` | `/api/generate` | Compile and write output files; returns `{files, dir}` |
| `GET` | `/api/fs/browse` | List subdirectories at `?path=<path>` (defaults to home) |
| `POST` | `/api/fs/mkdir` | Create a directory; body `{path}` |

---

## Running the backend separately (development)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Backend only (port 8000)
pip install -e .
uvicorn subgraph_wizard.server:app --port 8000 --reload

# Frontend dev server (port 5173, proxies /api → :8000)
cd frontend && npm install && npm run dev

# Build frontend into the static bundle
cd frontend && npm run build
```

---

## Interactive / config-driven modes

```bash
# Guided text wizard
subgraph-wizard

# Config-driven (non-interactive / CI)
subgraph-wizard --config subgraph-config.json --generate
subgraph-wizard --config subgraph-config.json --generate --dry-run
```

These modes produce a complete subgraph project from a `subgraph-config.json` file using
Jinja2 templates. They are separate from the visual editor and use their own data models.

---

## Environment variables

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `ETHERSCAN_API_KEY` | Etherscan API key (Ethereum mainnet) |
| `OPTIMISM_ETHERSCAN_API_KEY` | Optimism explorer API key |
| `ARBITRUM_ETHERSCAN_API_KEY` | Arbiscan API key |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`) |
| `VITE_API_PORT` | Override FastAPI port during frontend dev (default `8000`) |

---

## Tests

```bash
pytest          # 1160+ tests
pytest -v
pytest tests/test_validator.py
pytest tests/test_ponder_config.py
pytest tests/test_ponder_compiler.py
pytest tests/test_server.py
```

---

## Contributing

- Add new networks: edit `src/subgraph_wizard/networks.py`
- Add new ABI ingestion methods: extend `src/subgraph_wizard/abi/`
- Add new node types: add a React component in `frontend/src/nodes/`, update the compiler
  and validator in `src/subgraph_wizard/generate/`
- Add new mapping styles (CLI mode): extend `src/subgraph_wizard/generate/mappings_*.py`
