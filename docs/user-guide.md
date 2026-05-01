# Subgraph Wizard – User Guide

This guide explains how to use the Subgraph Wizard to create blockchain indexers.
The tool supports two output modes: **The Graph** (AssemblyScript subgraphs) and
**Ponder** (TypeScript indexers).  The canvas workflow is identical for both — switch
the output mode toggle in the toolbar before clicking Generate.

---

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd subgraph-wizard

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

### Verify Installation

```bash
subgraph-wizard --version
```

---

## Quick Start

### Interactive Wizard

The easiest way to create a subgraph is using the interactive wizard:

```bash
subgraph-wizard
```

The wizard will guide you through:
1. Subgraph name
2. Network selection
3. Contract configuration
4. ABI acquisition method
5. Mapping mode (stub vs auto)
6. Complexity level

### Config-Driven Generation

For non-interactive usage or automation, create a `subgraph-config.json` file and use:

```bash
subgraph-wizard --config subgraph-config.json --generate
```

---

## Complexity Levels

The wizard supports three complexity levels, each building upon the previous:

### Basic Complexity

**Use when**: You want to index events from one or more contracts.

**Features**:
- Event indexing
- Auto-generated or stub mappings
- Simple entity creation

**Example**: Indexing ERC-20 token transfers.

### Intermediate Complexity

**Use when**: You need call handlers or block handlers in addition to events.

**Features**:
- Everything in basic
- Call handlers (index function calls)
- Block handlers (index every block)

**Example**: Tracking token transfers via events AND function calls, plus block-level metrics.

### Advanced Complexity

**Use when**: You need dynamic data sources, templates, or entity relationships.

**Features**:
- Everything in intermediate
- Dynamic data source templates
- Entity relationships
- Multi-contract relationships

**Example**: Uniswap V2 subgraph with factory pattern (dynamic pairs) and entity relationships.

---

## ABI Acquisition Methods

The wizard supports three ways to provide contract ABIs:

### 1. Local File

Provide a path to a local JSON file containing the ABI:

```bash
# In the wizard, select "Local file" and provide the path
/path/to/contract.abi.json
```

### 2. Paste JSON

Paste the ABI JSON directly into the terminal:

```bash
# In the wizard, select "Paste JSON"
# Then paste your ABI and type END on a new line
[
  {
    "type": "event",
    "name": "Transfer",
    ...
  }
]
END
```

### 3. Fetch from Explorer

Automatically fetch ABIs from Etherscan-compatible explorers:

**Setup**:
1. Copy `.env.example` to `.env`
2. Add your API keys:
   ```
   ETHERSCAN_API_KEY=your_key_here
   OPTIMISM_ETHERSCAN_API_KEY=your_key_here
   ARBITRUM_ETHERSCAN_API_KEY=your_key_here
   ```

**Usage**: In the wizard, select "Fetch from explorer" and provide the contract address.

---

## Mapping Modes

### Auto Mode

**Best for**: Beginners and rapid prototyping.

**What it does**: Generates fully functional mapping handlers that automatically:
- Create entities for each event
- Populate entity fields from event parameters
- Add metadata (block number, timestamp, transaction hash)

**Example Output**:
```typescript
export function handleTransfer(event: TransferEvent): void {
  let entity = new Transfer(
    event.transaction.hash.toHex() + "-" + event.logIndex.toString()
  );
  entity.from = event.params.from;
  entity.to = event.params.to;
  entity.value = event.params.value;
  entity.blockNumber = event.block.number;
  entity.timestamp = event.block.timestamp;
  entity.txHash = event.transaction.hash;
  entity.save();
}
```

### Stub Mode

**Best for**: Advanced users who want full control.

**What it does**: Generates mapping handlers with TODO comments showing where to implement custom logic.

**Example Output**:
```typescript
export function handleTransfer(event: TransferEvent): void {
  // TODO: Implement transfer handler
  // Event params:
  //   - from: Address
  //   - to: Address
  //   - value: BigInt
  // 
  // Example:
  //   let entity = new Transfer(...);
  //   entity.from = event.params.from;
  //   entity.to = event.params.to;
  //   entity.value = event.params.value;
  //   entity.save();
}
```

---

## Advanced Complexity Examples

### Example 1: Factory Pattern with Dynamic Data Sources

This example shows how to index a factory contract that creates new contracts at runtime (e.g., Uniswap V2).

**Config** (`subgraph-config.json`):
```json
{
  "config_version": 3,
  "name": "uniswap-v2-subgraph",
  "network": "ethereum",
  "output_dir": "output/uniswap-v2",
  "complexity": "advanced",
  "mappings_mode": "auto",
  "contracts": [
    {
      "name": "Factory",
      "address": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
      "start_block": 10000835,
      "abi_path": "Factory.json",
      "index_events": true
    }
  ],
  "templates": [
    {
      "name": "Pair",
      "abi_path": "Pair.json",
      "event_handlers": ["Swap", "Sync", "Mint", "Burn"],
      "source_contract": "Factory",
      "source_event": "PairCreated",
      "index_events": true
    }
  ]
}
```

**What this does**:
1. Indexes the `Factory` contract starting at block 10000835
2. When `Factory` emits `PairCreated`, automatically creates a new data source for that `Pair` contract
3. Indexes `Swap`, `Sync`, `Mint`, and `Burn` events from each dynamically created `Pair`

**Generated Code**: The wizard automatically generates mapping code that:
- Handles `PairCreated` events from the factory
- Instantiates new `Pair` data sources using the template
- Handles events from all instantiated pairs

### Example 2: Entity Relationships

This example adds entity relationships to link related entities in the schema.

**Config** (extending Example 1):
```json
{
  "config_version": 3,
  "name": "uniswap-v2-subgraph",
  "network": "ethereum",
  "output_dir": "output/uniswap-v2",
  "complexity": "advanced",
  "mappings_mode": "auto",
  "contracts": [
    {
      "name": "Factory",
      "address": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
      "start_block": 10000835,
      "abi_path": "Factory.json",
      "index_events": true
    }
  ],
  "templates": [
    {
      "name": "Pair",
      "abi_path": "Pair.json",
      "event_handlers": ["Swap", "Sync", "Mint", "Burn"],
      "source_contract": "Factory",
      "source_event": "PairCreated",
      "index_events": true
    }
  ],
  "entity_relationships": [
    {
      "from_entity": "Swap",
      "to_entity": "Factory",
      "relation_type": "one_to_one",
      "field_name": "factory"
    },
    {
      "from_entity": "Factory",
      "to_entity": "Swap",
      "relation_type": "one_to_many",
      "field_name": "swaps",
      "derived_from": "factory"
    }
  ]
}
```

**What this does**:
1. Creates a `factory` field on `Swap` entities (one-to-one relationship)
2. Creates a `swaps` field on `Factory` entities (one-to-many relationship, derived from the reverse reference)

**Generated Schema**:
```graphql
type Swap @entity {
  id: ID!
  # ... event fields ...
  factory: Factory!
}

type Factory @entity {
  id: ID!
  # ... factory fields ...
  swaps: [Swap!]!  # Derived field
}
```

### Example 3: Intermediate Complexity with Call Handlers

This example shows how to use call handlers to track function calls in addition to events.

**Config**:
```json
{
  "config_version": 2,
  "name": "token-with-calls",
  "network": "ethereum",
  "output_dir": "output/token-calls",
  "complexity": "intermediate",
  "mappings_mode": "auto",
  "contracts": [
    {
      "name": "Token",
      "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
      "start_block": 12345678,
      "abi_path": "Token.json",
      "index_events": true,
      "call_handlers": [
        "transfer(address,uint256)",
        "approve(address,uint256)"
      ],
      "block_handler": false
    }
  ]
}
```

**What this does**:
1. Indexes all events from the `Token` contract
2. Also indexes calls to `transfer` and `approve` functions
3. Generates handlers for both events and function calls

---

## Ponder output mode

Ponder produces a self-hosted TypeScript indexer that runs on Node.js and exposes a live
GraphQL API. Use it when you want:

- Full TypeScript control over handler logic.
- Multi-chain indexing in a single process.
- A real-time GraphQL API without deploying to The Graph.

### Visual editor quick-start (Ponder)

1. Open the canvas (`subgraph-wizard --ui`).
2. Toggle the **Output mode** to **Ponder** in the top toolbar.
3. Build your canvas exactly as you would for a subgraph (Contract → Entity / Aggregate Entity
   nodes, Networks panel for addresses and start blocks).
4. Click **Generate**. The modal shows a **Ponder Settings** section:
   - **Database** — `PGlite` (zero-config, embedded) or `PostgreSQL` (production).
   - **Ordering** — `multichain` (default), `omnichain`, or `experimental_isolated`.
5. Choose an output directory and click **Generate**.

### Generated files

| File | Description |
|---|---|
| `ponder.config.ts` | Chain RPC config, contract addresses, and start blocks |
| `ponder.schema.ts` | Ponder `onchainTable` definitions (one per entity node) |
| `src/index.ts` | TypeScript event handlers compiled from your canvas |
| `src/api/index.ts` | Hono HTTP app; mounts `/graphql` and `/` |
| `ponder-env.d.ts` | Ponder environment typings |
| `tsconfig.json` | TypeScript project config |
| `package.json` | `pnpm dev`, `pnpm start`, `pnpm codegen` scripts |
| `.env.example` | RPC URL placeholders (one per chain) |
| `PONDER_HOWTO.md` | Step-by-step guide generated for your specific canvas |

### Key behaviours

**Auto `chain` field.** Every entity table gets a `chain text NOT NULL` column added
automatically after `id`. Every insert sets it to `context.chain.name`. This means you
can filter or group results by chain in GraphQL queries without any extra canvas wiring.

**Multi-chain, one indexer.** All networks in the Networks panel are indexed concurrently
inside one Ponder process and stored in the same database. The `chain` column keeps records
from different networks distinct.

**Suffix-retry inserts.** Ponder rejects duplicate primary keys. The generated handlers
retry with a `-1`, `-2`, … suffix appended to the record ID until the insert succeeds,
preventing silently dropped events.

**GraphQL at `/graphql`.** Since Ponder 0.8 the GraphQL endpoint is not served
automatically. The generated `src/api/index.ts` mounts it explicitly. Start the indexer
with `pnpm dev` and open `http://localhost:42069/graphql` (or `/` for the GraphiQL
playground).

**startBlock auto-detection.** If a contract instance has no start block set (or 0),
the generator queries Etherscan to find the deployment block automatically, provided
`ETHERSCAN_API_KEY` is set in the environment. This mirrors the behaviour of the
The Graph output mode.

### Running the indexer

```bash
cd <output-directory>
cp .env.example .env.local
# Edit .env.local — set PONDER_RPC_URL_<chainId> for each chain
pnpm install
pnpm dev      # starts indexer + hot-reload; GraphQL at http://localhost:42069/graphql
```

See the generated `PONDER_HOWTO.md` for the complete walkthrough including production
deployment.

---

## Workflow

### Step 1: Create Config

**Option A - Interactive Wizard**:
```bash
subgraph-wizard
# Follow the prompts
```

**Option B - Manual Config**:
Create `subgraph-config.json` following the [Config Format](config-format.md) documentation.

### Step 2: Generate Subgraph

```bash
subgraph-wizard --config subgraph-config.json --generate
```

Or, if you used the interactive wizard and saved the config:
```bash
cd <output_dir>
subgraph-wizard --config subgraph-config.json --generate
```

### Step 3: Build and Deploy

The generated subgraph includes a README with build instructions. Typically:

```bash
cd <output_dir>
npm install
graph codegen
graph build
graph deploy --node <node-url> <subgraph-name>
```

---

## Dry Run Mode

Preview what will be generated without writing files:

```bash
subgraph-wizard --config subgraph-config.json --generate --dry-run
```

This will log:
- File paths that would be created
- File sizes
- Preview of first ~200 characters of each file

---

## Troubleshooting

### Visual editor — fields are null or wrong in the deployed subgraph

Two common causes:

**1. Unwired field name doesn't match the event parameter name.**
Auto-fill only kicks in when the entity field name matches an event parameter name exactly
(case-sensitive). Check the field name in your Entity node against the parameter names shown
on the Contract node's event chevron (click `▶` to expand a trigger).

**2. Contract address not set in the Networks panel.**
The compiler reads the deployed address from the **Networks panel**, not from the inline
address box on the Contract node. Open the Networks panel and add the deployed address under
the contract's Instances section.

### Visual editor — TS2322 type error from `graph build`

```
ERROR TS2322: Type 'Bytes' is not assignable to type 'Array<BigInt> | null'
   entity.accounts = event.params.accounts
```

The entity field type does not match the event parameter type. The current compiler catches
this at generate time and reports it as a human-readable error before writing any files — if
you see it in `graph build`, you are building files generated by an older version.

Fix: hit **Generate** again to regenerate. When prompted with the type-mismatch error,
go to the Entity node and change the field type to match the event param type (visible on
the Contract node's expanded event chevron).

### Visual editor — indexed array parameter shows as `Bytes`

If an event parameter's type on the Contract node is `Bytes` but you expected
`[BigInt!]` or `[Address!]`, check whether the parameter is marked `indexed` in the ABI.

In Ethereum, **indexed reference-type parameters** (arrays, `bytes`, `string`, tuples) are
stored as their keccak256 hash in the log topic — the actual array values are not
recoverable at indexing time. graph-cli correctly generates `Bytes` for these, and this
tool's ABI parser does the same.

Consequence: you cannot store the actual array elements from an indexed array parameter.
Options:
- Use the `Bytes` hash as an opaque fingerprint (you can store and compare it).
- Listen for individual per-item events instead (e.g. a separate `Liquidated` event per
  account alongside a `BatchLiquidated` summary event).
- Read the values from transaction calldata (requires custom decoding, not supported
  natively by The Graph).

### Visual editor — entity field type is stale after re-parsing the ABI

Re-parsing the ABI on the Contract node updates the event port types on the Contract node.
It does **not** retroactively update field types on Entity or Aggregate Entity nodes you
already created. If a param type changed (e.g. from `[BigInt!]` to `Bytes` after the
indexed-type fix), go to each affected Entity node and manually correct the field:

1. Click the type dropdown → select the correct scalar type.
2. If the field was in list mode (the `[ ]` button is highlighted), click it to deactivate.

### Visual editor — generate reports "auto-fill type mismatch"

```
Auto-fill type mismatch in entity 'MyEntity', field 'accounts':
  Entity field type : [BigInt!]
  Event param type  : Bytes
```

The entity field type and the matching event parameter type are different. The compiler
refuses to silently produce a null field. Fix the entity field type to match the param type
shown in the error message, or draw an explicit wire through a Type Cast node for
intentional conversions.

### Visual editor — subgraph syncs from block 0

The `startBlock` in the Networks panel is 0 or unset. Set it to the block number of the
contract's deployment transaction (find it on Etherscan or a block explorer). Indexing from
block 0 forces The Graph to scan the entire chain history, which can take days.

### "Network not supported"

Make sure the network name matches one of the supported networks. Check `networks.py` for the full list.

### "Invalid contract address"

Contract addresses must be:
- Prefixed with `0x`
- Exactly 42 characters total (0x + 40 hex chars)
- Valid hexadecimal

### "ABI fetch failed"

If fetching from explorer fails:
1. Check your API key in `.env`
2. Verify the contract is verified on the explorer
3. Try using a local ABI file or pasting the ABI instead

### "Template source contract not found"

When using templates, ensure:
- `source_contract` matches a contract name in the `contracts` array
- The contract name is spelled exactly (case-sensitive)

### "Validation error: complexity mismatch"

Advanced features (templates, relationships) require `complexity: "advanced"`. Make sure your config version and complexity level match.

---

## Best Practices

1. **Start Simple**: Begin with basic complexity and upgrade as needed
2. **Use Auto Mode First**: Get a working subgraph quickly, then customize if needed
3. **Version Control**: Commit your `subgraph-config.json` to track changes
4. **Test Locally**: Use `--dry-run` to preview before generating
5. **ABI Management**: Keep ABI files in version control for reproducibility
6. **Start Blocks**: Set accurate start blocks to avoid indexing unnecessary data

---

## Next Steps

- Read the [Config Format](config-format.md) documentation for complete field reference
- Check the [Architecture](architecture.md) documentation to understand the system design
- Review [Development Notes](development-notes.md) if you want to contribute

---

## See Also

- [The Graph Documentation](https://thegraph.com/docs/)
- [AssemblyScript Documentation](https://www.assemblyscript.org/)
- [GraphQL Schema Reference](https://thegraph.com/docs/en/developer/create-subgraph-hosted/#the-subgraph-manifest)
