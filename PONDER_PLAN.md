# Ponder Output Mode — Design Plan

Branch: `ponder`

## Overview

Add a toggle to the canvas that switches the **output target** between:
- **The Graph** (current behaviour) — generates `subgraph.yaml`, `schema.graphql`, AssemblyScript mappings
- **Ponder** — generates `ponder.config.ts`, `ponder.schema.ts`, TypeScript handlers (`src/index.ts`), TypeScript ABI files

The canvas node graph is **identical** in both modes. The same contract, entity, math, typecast, conditional, and contractread nodes work unchanged. Only the files that come out the other end differ.

---

## What Ponder Expects

A minimal Ponder project (confirmed from live ERC-20 example):

```
project/
├── ponder.config.ts        # createConfig({ chains, contracts })
├── ponder.schema.ts        # onchainTable(...) per entity
├── ponder-env.d.ts         # static boilerplate — reference types
├── tsconfig.json           # standard TypeScript config
├── package.json            # { ponder, drizzle-kit, hono, viem }
├── .env.example            # PONDER_RPC_URL_1=https://...
├── abis/
│   └── ERC20Abi.ts         # export const ERC20Abi = [...] as const
└── src/
    └── index.ts            # all event handlers in one file
```

### ponder.config.ts

```ts
import { createConfig } from "ponder";
import { ERC20Abi } from "./abis/ERC20Abi";

export default createConfig({
  chains: {
    mainnet: { id: 1, rpc: process.env.PONDER_RPC_URL_1 },
  },
  contracts: {
    ERC20: {
      chain: "mainnet",
      abi: ERC20Abi,
      address: "0x...",
      startBlock: 13142655,
    },
  },
});
```

### ponder.schema.ts

```ts
import { onchainTable } from "ponder";

export const transfer = onchainTable("transfer", (t) => ({
  id:        t.text().primaryKey(),
  from:      t.hex().notNull(),
  to:        t.hex().notNull(),
  amount:    t.bigint().notNull(),
  timestamp: t.integer().notNull(),
}));
```

### src/index.ts

```ts
import { ponder } from "ponder:registry";
import { transfer } from "ponder:schema";

ponder.on("ERC20:Transfer", async ({ event, context }) => {
  await context.db.insert(transfer).values({
    id:        event.id,
    from:      event.args.from,
    to:        event.args.to,
    amount:    event.args.amount,
    timestamp: Number(event.block.timestamp),
  });
});
```

### abis/ERC20Abi.ts

```ts
export const ERC20Abi = [
  { type: "event", name: "Transfer", inputs: [...], ... },
  ...
] as const;
```

---

## Mapping: Existing Nodes → Ponder Output

### Field type mapping

| Graph type  | AssemblyScript   | Ponder schema      | TypeScript native  |
|-------------|------------------|--------------------|---------------------|
| `ID`        | `string`         | `t.text().primaryKey()` | `string`       |
| `String`    | `string`         | `t.text()`         | `string`            |
| `BigInt`    | `BigInt`         | `t.bigint()`       | `bigint`            |
| `Int`       | `i32`            | `t.integer()`      | `number`            |
| `Boolean`   | `boolean`        | `t.boolean()`      | `boolean`           |
| `Bytes`     | `Bytes`          | `t.hex()`          | `` `0x${string}` `` |
| `Address`   | `Address`        | `t.hex()`          | `` `0x${string}` `` |
| `BigDecimal`| `BigDecimal`     | **see note below** | `number` or `string`|

> **BigDecimal open question** — Ponder has no native decimal type.
> Options: `t.real()` (float64, slightly lossy for fractional token values),
> `t.text()` (exact but loses arithmetic), or disallow in Ponder mode with a
> validator warning. See *Open Questions* below.

### Event field access

| What                 | The Graph (AS)              | Ponder (TS)                      |
|----------------------|-----------------------------|----------------------------------|
| Event param `x`      | `event.params.x`            | `event.args.x`                   |
| Tx hash              | `event.transaction.hash`    | `event.transaction.hash`         |
| Block number         | `event.block.number`        | `event.block.number`             |
| Block timestamp      | `event.block.timestamp`     | `Number(event.block.timestamp)`  |
| Log address          | `event.address`             | `event.log.address`              |
| Unique event ID      | `txHash + "-" + logIndex`  | `event.id` (built-in)            |

### Entity node (immutable insert)

**The Graph AS:**
```ts
let e = new Transfer(id)
e.amount = event.params.amount
e.save()
```

**Ponder TS:**
```ts
await context.db.insert(transfer).values({
  id:     event.id,
  amount: event.args.amount,
})
```

### Aggregate entity node (mutable upsert)

**The Graph AS:**
```ts
let e = TVL.load("global") ?? new TVL("global")
e.balance = e.balance.plus(event.params.amount)
e.save()
```

**Ponder TS:**
```ts
await context.db
  .insert(tvl)
  .values({ id: "global", balance: event.args.amount })
  .onConflictDoUpdate((row) => ({
    balance: row.balance + event.args.amount,
  }))
```

The `field-in-*` wire supplies the delta; `field-prev-*` wires that currently
expose previous values for downstream nodes still apply (Ponder's
`onConflictDoUpdate` callback receives the existing row as `row`).

### Math node

| Operation  | AssemblyScript                | Ponder TS     |
|------------|-------------------------------|---------------|
| add        | `a.plus(b)`                   | `a + b`       |
| subtract   | `a.minus(b)`                  | `a - b`       |
| multiply   | `a.times(b)`                  | `a * b`       |
| divide     | `a.div(b)`                    | `a / b`       |
| mod        | `a.mod(b)`                    | `a % b`       |
| pow        | `a.pow(b.toI32())`            | `a ** b`      |

All bigint arithmetic uses native TypeScript `bigint` operators — no library needed.

### TypeCast node

| Cast                    | AssemblyScript                  | Ponder TS                     |
|-------------------------|---------------------------------|-------------------------------|
| BigInt → Int            | `.toI32()`                      | `Number(x)`                   |
| BigInt → String         | `.toString()`                   | `x.toString()`                |
| Bytes → String (hex)    | `.toHexString()`                | `x` (already `0x${string}`)   |
| Bytes → Address         | `Address.fromBytes(x)`          | `x` (same type `0x${string}`) |
| String → Bytes          | `ByteArray.fromHexString(x)`    | `x as \`0x\${string}\``       |
| Address → Bytes         | (same type)                     | `x` (same type)               |
| Address → String        | `.toHexString()`                | `x` (already string)          |

### String concat node

**The Graph AS:** `left.concat(" ").concat(right)`
**Ponder TS:** `` `${left}${separator}${right}` ``

### Conditional node

**The Graph AS:** emits `let cond = expr; if (cond) { entity.field = value }`
**Ponder TS:** same pattern — `const cond = expr; if (cond) { ... }` — simpler
because no declared_vars dedup is needed (plain TS closures handle scope).

### Contract read node

**The Graph AS:**
```ts
const c = MyContract.bind(addr)
const r = c.try_balanceOf(arg)
const val = r.reverted ? BigInt.zero() : r.value
```

**Ponder TS:**
```ts
const val = await context.client.readContract({
  abi:          MyContractAbi,
  address:      addr,
  functionName: "balanceOf",
  args:         [arg],
  blockNumber:  event.block.number,
})
```

---

## Files to Create / Modify

### New backend files

```
src/subgraph_wizard/generate/
├── ponder_compiler.py      # PonderCompiler class — mirrors GraphCompiler
│                           # but emits TypeScript
├── ponder_schema.py        # generate ponder.schema.ts from entity nodes
└── ponder_config.py        # generate ponder.config.ts + ponder-env.d.ts
                            # + tsconfig.json + package.json + .env.example
```

### Existing files modified

| File | Change |
|------|--------|
| `server.py` | Route `POST /api/generate` based on `visual_config["outputMode"]` |
| `validator.py` | Add `PONDER_BIGDECIMAL_UNSUPPORTED` warning (if we disallow BigDecimal) |
| `frontend/src/components/TopToolbar.jsx` (or similar) | Add mode toggle switch |
| `frontend/src/hooks/useValidation.js` | Pass `outputMode` in validate request |

### No changes needed

- All canvas node types (contract, entity, aggregateentity, math, typecast,
  strconcat, conditional, contractread) — unchanged
- Validator topology checks — all still apply in Ponder mode
- `build_entity_name_map()` — reused as-is
- `_find_reachable_entities()` — logic reused in `PonderCompiler`

---

## `PonderCompiler` Architecture

`PonderCompiler` mirrors `GraphCompiler` structurally but emits TypeScript.

```python
class PonderCompiler:
    def __init__(self, visual_config): ...

    def compile(self) -> dict[str, str]:
        """Returns {"index.ts": <handler source>}."""
        ...

    def _compile_handler(self, contract_type, event_name, event_params, entities) -> str:
        """Emit one ponder.on("Contract:Event", async ({event, context}) => {...}) block."""
        ...

    def _compile_entity_insert(self, entity_node, event_name, ...) -> list[str]:
        """Emit context.db.insert(...).values({...}) for a regular entity."""
        ...

    def _compile_aggregate_upsert(self, agg_node, event_name, ...) -> list[str]:
        """Emit context.db.insert(...).values({...}).onConflictDoUpdate(row => ({...}))."""
        ...

    def _resolve_value_ts(self, source_node_id, source_handle, ...) -> tuple[str, list[str]]:
        """Like _resolve_value but emits TypeScript (bigint operators, async awaits)."""
        ...
```

All graph traversal (BFS, edge lookups, port resolution) is the same as
`GraphCompiler`. Only terminal code emission differs.

---

## Frontend Toggle

A simple two-state toggle in the top toolbar. Stored in `visual_config` so it
persists with the project file.

```
┌─────────────────────────────────────────────────────┐
│  [◉ The Graph]  [○ Ponder]     [Validate] [Generate] │
└─────────────────────────────────────────────────────┘
```

State key: `visual_config.outputMode` — `"graph"` (default) or `"ponder"`.

The generate button label changes to reflect the target:
- **The Graph**: "Generate Subgraph"
- **Ponder**: "Generate Ponder App"

The validate button remains identical (validator is mode-agnostic; same
warnings apply in both modes).

---

## Chain ID Lookup

Ponder requires a numeric `id` per chain. We'll hardcode a lookup table for
common networks (user can extend for unusual chains):

```python
CHAIN_IDS = {
    "mainnet":        1,
    "sepolia":        11155111,
    "holesky":        17000,
    "polygon":        137,
    "polygon-mumbai": 80001,
    "arbitrum-one":   42161,
    "arbitrum-sepolia":421614,
    "optimism":       10,
    "base":           8453,
    "base-sepolia":   84532,
    "avalanche":      43114,
    "bsc":            56,
    "gnosis":         100,
    "fantom":         250,
    "zksync-era":     324,
    "linea":          59144,
    "scroll":         534352,
}
```

If a network name isn't in the table, we fall back to `id: 0` and emit a
validator warning `PONDER_UNKNOWN_CHAIN_ID`.

---

## Open Questions

Before implementing, I need answers to these:

### 1. BigDecimal mapping

Ponder has no native arbitrary-precision decimal type. For fields declared as
`BigDecimal` in the schema, three options:

- **`t.real()`** — stores as IEEE 754 float64. Exact for values up to ~15
  significant digits. Loses precision for very large fractional token amounts.
  Simplest to generate.
- **`t.text()`** — stores the decimal as a string. Exact, but arithmetic in
  handlers must use a library (e.g., `decimal.js`). More complex to generate.
- **Validator warning** — emit `PONDER_BIGDECIMAL_UNSUPPORTED` and tell the
  user to replace BigDecimal fields with BigInt (store in wei/base units) or
  String. The most honest option for now.

**My recommendation**: validator warning for BigDecimal + suggest BigInt.
Most EVM contracts work in integer base units anyway.

### 2. Database target

Should `ponder.config.ts` default to:
- **No `database:` key** — Ponder defaults to PGlite (zero-config, embedded
  Postgres, perfect for development)
- **Prompt in UI** — add a "Database" selector to the canvas (PGlite / PostgreSQL)

**My recommendation**: omit `database:` by default (PGlite). Add a `.env.example`
with `DATABASE_URL=` commented out so users know where to set it for production.

### 3. Multi-network projects

The Networks panel already supports multiple networks (e.g., mainnet + Sepolia).
In Ponder, each contract picks one chain. Should we:
- Generate one ponder.config.ts with all configured networks in `chains:` and
  each contract assigned to its configured chain
- Or limit Ponder mode to single-network projects for now?

**My recommendation**: full multi-network support — it maps cleanly to Ponder's
`chains:` + `chain:` model.

### 4. `.env.example`

Should we generate a `.env.example` showing the RPC URL env vars? Ponder
convention is `PONDER_RPC_URL_{chainId}` (e.g., `PONDER_RPC_URL_1` for mainnet).

**My recommendation**: yes, always generate `.env.example` with one line per chain.

### 5. `howto.md` equivalent

The current generator produces a `howto.md` with deployment instructions.
Should we produce a Ponder-specific version explaining `pnpm install`,
`pnpm dev`, and how to connect a database?

**My recommendation**: yes, generate a `PONDER_HOWTO.md` with the quickstart steps.

---

## What We Are NOT Doing (v1 scope)

- **Block interval handlers** — the `blocks:` config key isn't representable
  with current node types. Future: add a "Block Interval" node type.
- **Setup handlers** — `ponder.on("Contract:setup", ...)` for initialization.
  Future: add a "Setup" node or flag on entity nodes.
- **Factory pattern** — `factory({...})` for dynamic addresses. Future: add
  a "Factory" mode to the contract node.
- **Call trace handlers** — requires `includeCallTraces: true` and a different
  wiring model. Future work.
- **Account/transaction indexing** — Ponder's `accounts:` config. Not in scope.

---

## Implementation Order

1. **Frontend toggle** — add `outputMode` to visual config, persist it, show
   toggle in top toolbar. No backend change yet; just UI state.

2. **`ponder_schema.py`** — generate `ponder.schema.ts` from entity/aggregate
   nodes. Straightforward type mapping. Write tests first.

3. **`ponder_config.py`** — generate `ponder.config.ts`, `ponder-env.d.ts`,
   `tsconfig.json`, `package.json`, `.env.example`. Mostly templates.

4. **ABI TypeScript files** — convert JSON ABI arrays to
   `export const XAbi = [...] as const`. Trivial conversion.

5. **`ponder_compiler.py`** — the main work. Emit `src/index.ts` with handlers.
   Start with regular entity inserts, then add aggregate upserts, then math/
   typecast/strconcat, then conditional, then contractread.

6. **`server.py` routing** — add `outputMode` branch to `POST /api/generate`.

7. **Validator additions** — `PONDER_BIGDECIMAL_UNSUPPORTED`,
   `PONDER_UNKNOWN_CHAIN_ID` (only raised in ponder mode).

8. **Tests** — pytest for each generator, vitest for the toggle UI.
