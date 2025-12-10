# Subgraph Wizard – User Guide

This guide explains how to use the Subgraph Wizard to create subgraph projects for The Graph.

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
