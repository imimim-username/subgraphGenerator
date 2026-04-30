# Subgraph Config Format

This document describes the complete format of `subgraph-config.json`, the configuration file used by Subgraph Wizard to generate subgraph projects.

The config format supports three complexity levels: **basic**, **intermediate**, and **advanced**. Each level builds upon the previous one, adding new capabilities while maintaining backward compatibility.

---

## Config Versioning

The `config_version` field indicates which schema version the config uses:

- **Version 1**: Basic complexity only (events)
- **Version 2**: Adds intermediate complexity (call/block handlers)
- **Version 3**: Adds advanced complexity (templates, entity relationships)

The wizard automatically sets the appropriate version based on the complexity level you choose. Older version configs remain fully supported and are automatically upgraded when loaded.

---

## Top-Level Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Subgraph name (used in project directory and `package.json`) |
| `network` | `string` | Network identifier (must be one of: `ethereum`, `optimism`, `arbitrum`, etc.) |
| `output_dir` | `string` | Directory where the subgraph project will be generated |
| `mappings_mode` | `string` | Mapping generation mode: `"stub"` or `"auto"` |
| `contracts` | `array` | List of contracts to index (see [ContractConfig](#contractconfig) below) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `config_version` | `integer` | `1` | Configuration schema version (1, 2, or 3) |
| `complexity` | `string` | `"basic"` | Complexity level: `"basic"`, `"intermediate"`, or `"advanced"` |
| `templates` | `array` | `[]` | List of dynamic data source templates (advanced complexity only) |
| `entity_relationships` | `array` | `[]` | List of relationships between entities (advanced complexity only) |

---

## ContractConfig

Each contract in the `contracts` array is a `ContractConfig` object with the following fields:

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Human-readable name for the contract (used in entity naming) |
| `address` | `string` | Contract address (must be `0x` + 40 hex characters) |
| `start_block` | `integer` | Block number to start indexing from |
| `abi_path` | `string` | Filename of the ABI JSON file (relative to `abis/` directory) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `index_events` | `boolean` | `true` | Whether to index events from this contract |
| `call_handlers` | `array<string>` | `null` | List of function signatures to index (intermediate/advanced complexity) |
| `block_handler` | `boolean` | `false` | Whether to enable block handler for this contract (intermediate/advanced complexity) |

### Call Handlers

Call handlers allow you to index function calls to contracts. Each entry in `call_handlers` should be a function signature in the format:

```
functionName(paramType1,paramType2,...)
```

Examples:
- `"transfer(address,uint256)"`
- `"approve(address,uint256)"`
- `"mint(address,uint256)"`

**Note**: Call handlers are only available for `intermediate` and `advanced` complexity levels.

### Block Handlers

When `block_handler` is `true`, a handler will be called for every block. This is useful for tracking block-level metrics or state changes that don't correspond to specific events.

**Note**: Block handlers are only available for `intermediate` and `advanced` complexity levels.

---

## TemplateConfig (Advanced Complexity)

Templates are used for dynamic data sources—contracts whose addresses are not known at deployment time. They are instantiated at runtime when a factory contract emits a specific event.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Template name (used in `subgraph.yaml` templates section) |
| `abi_path` | `string` | Filename of the ABI JSON file (relative to `abis/` directory) |
| `event_handlers` | `array<string>` | List of event names to handle in the template (must be non-empty) |
| `source_contract` | `string` | Name of the factory contract that instantiates this template |
| `source_event` | `string` | Event name that triggers template instantiation (e.g., `"PairCreated"`) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `index_events` | `boolean` | `true` | Whether to index events from instantiated contracts |
| `call_handlers` | `array<string>` | `null` | List of function signatures to index for instantiated contracts |
| `block_handler` | `boolean` | `false` | Whether to enable block handler for instantiated contracts |

### Example Use Case

Uniswap V2 uses a factory pattern where the `Factory` contract emits a `PairCreated` event when a new trading pair is created. Each new `Pair` contract should be indexed dynamically:

```json
{
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

---

## EntityRelationship (Advanced Complexity)

Entity relationships define how entities in the GraphQL schema relate to each other. This enables generating proper schema with references and derived fields.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `from_entity` | `string` | Name of the source entity (must match a contract name or event entity) |
| `to_entity` | `string` | Name of the target entity |
| `relation_type` | `string` | Type of relationship: `"one_to_one"`, `"one_to_many"`, or `"many_to_many"` |
| `field_name` | `string` | Field name on the source entity for this relationship |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `derived_from` | `string` | `null` | For derived fields, the field on the target entity that references back to this entity (used for reverse lookups) |

### Relationship Types

- **`one_to_one`**: Single reference (e.g., `Token -> Owner`)
- **`one_to_many`**: Array of references (e.g., `Factory -> [Pool]`)
- **`many_to_many`**: Many-to-many via join (e.g., `User <-> Token`)

### Example

```json
{
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

---

## Complete Examples

### Basic Complexity (Version 1)

```json
{
  "config_version": 1,
  "name": "my-token-subgraph",
  "network": "ethereum",
  "output_dir": "./generated-subgraph",
  "complexity": "basic",
  "mappings_mode": "auto",
  "contracts": [
    {
      "name": "TestToken",
      "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
      "start_block": 12345678,
      "abi_path": "TestToken.json",
      "index_events": true
    }
  ]
}
```

### Intermediate Complexity (Version 2)

```json
{
  "config_version": 2,
  "name": "token-with-handlers",
  "network": "ethereum",
  "output_dir": "./generated-subgraph",
  "complexity": "intermediate",
  "mappings_mode": "auto",
  "contracts": [
    {
      "name": "TestToken",
      "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
      "start_block": 12345678,
      "abi_path": "TestToken.json",
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

### Advanced Complexity (Version 3)

See `tests/fixtures/advanced_config.json` for a complete example with templates and entity relationships.

---

## Validation Rules

- **Network**: Must be one of the supported networks (see `networks.py`)
- **Address**: Must be a valid hex address (`0x` + 40 hex characters)
- **Complexity**: Must be `"basic"`, `"intermediate"`, or `"advanced"`
- **Mappings Mode**: Must be `"stub"` or `"auto"`
- **Templates**: Can only be used when `complexity == "advanced"`
- **Entity Relationships**: Can only be used when `complexity == "advanced"`
- **Call/Block Handlers**: Can only be used when `complexity == "intermediate"` or `"advanced"`
- **Template Event Handlers**: Must be non-empty
- **Template Source Contract**: Must reference a contract name that exists in `contracts`

---

## Backward Compatibility

- Version 1 configs are fully supported and work with basic complexity
- Version 2 configs are supported and work with intermediate complexity
- Version 3 configs are required for advanced complexity features
- When loading older configs, advanced fields are initialized with defaults (empty lists, `false`)

---

## See Also

- [User Guide](user-guide.md) – How to use the wizard and create configs
- [Architecture](architecture.md) – Internal system design
- [Development Notes](development-notes.md) – Contributing guidelines
