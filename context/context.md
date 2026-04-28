# Project Context

## What this is

**Subgraph Wizard** — a Python CLI tool (v0.1.0) that auto-generates ready-to-deploy
subgraph projects for [The Graph](https://thegraph.com/) protocol. Users answer
guided questions or supply a config file; the tool outputs a fully structured
subgraph project (YAML manifest, GraphQL schema, TypeScript mappings, package.json,
README) that can be built and deployed with standard Graph tooling.

Two operating modes:

**Interactive wizard** — guided Q&A flow:
```bash
subgraph-wizard
```

**Config-driven** — load a pre-created config file and generate immediately:
```bash
subgraph-wizard --config subgraph-config.json --generate
```

---

## File structure

```
subgraphGenerator/
├── src/subgraph_wizard/
│   ├── main.py                  # CLI entry point, error handling, Ctrl+C
│   ├── cli.py                   # argparse: --config, --generate, --dry-run, --output-dir
│   ├── interactive_wizard.py    # Interactive Q&A flow (run_wizard())
│   ├── networks.py              # SUPPORTED_NETWORKS dict: ethereum/optimism/arbitrum
│   ├── logging_setup.py         # Logging config (LOG_LEVEL env var)
│   ├── errors.py                # SubgraphWizardError, ValidationError, AbiFetchError
│   ├── config/
│   │   ├── model.py             # SubgraphConfig, ContractConfig, TemplateConfig, EntityRelationship dataclasses
│   │   ├── io.py                # load_config() / save_config() — JSON read/write
│   │   └── validation.py        # Comprehensive config validation
│   ├── abi/
│   │   ├── local.py             # Load ABI from local JSON file
│   │   ├── paste.py             # Interactive ABI paste (reads until "END" sentinel)
│   │   ├── etherscan.py         # Fetch ABI from Etherscan-compatible explorer APIs
│   │   └── utils.py             # ABI parsing, event extraction, Solidity→GQL type mapping
│   ├── generate/
│   │   ├── orchestrator.py      # Main generation pipeline — coordinates all steps
│   │   ├── project_layout.py    # Creates abis/, src/mappings/, generated/ directories
│   │   ├── subgraph_yaml.py     # Generates subgraph.yaml manifest
│   │   ├── schema.py            # Generates schema.graphql
│   │   ├── mappings_auto.py     # Generates fully functional TypeScript handlers
│   │   ├── mappings_stub.py     # Generates stub TypeScript handlers with TODOs
│   │   ├── package_json.py      # Generates package.json
│   │   └── readme.py            # Generates README.md for the output subgraph
│   └── utils/
│       ├── fs_utils.py          # Safe file I/O, path helpers
│       ├── templating.py        # Jinja2 wrapper
│       └── prompts_utils.py     # Reusable prompt/input helpers
├── templates/                   # Jinja2 template files
│   ├── subgraph.yaml.j2
│   ├── README.generated.md.j2
│   ├── package.json.j2
│   ├── schema/
│   │   └── base_schema.graphql.j2
│   └── mappings/
│       ├── common_header.ts.j2
│       ├── mapping_stub.ts.j2
│       └── mapping_auto.ts.j2
├── tests/
│   ├── fixtures/                # Test configs (basic/advanced) and sample ABIs
│   ├── test_cli.py
│   ├── test_config_io.py
│   ├── test_validation.py
│   ├── test_abi_*.py
│   ├── test_generate_*.py
│   ├── test_interactive_wizard*.py
│   └── test_full_generation*.py
├── examples/
│   └── basic-single-contract/subgraph-config.json
├── docs/
│   ├── architecture.md
│   ├── config-format.md
│   ├── user-guide.md
│   └── development-notes.md
├── pyproject.toml               # Package metadata, deps, entry point
├── .env.example
└── development_checklist.md     # Development roadmap
```

---

## Core data models (`config/model.py`)

All are Python dataclasses.

**`SubgraphConfig`** — top-level
- `name`, `network`, `output_dir`, `mappings_mode` (`"auto"` or `"stub"`)
- `config_version`: 1=basic, 2=intermediate, 3=advanced
- `complexity`: `"basic"` | `"intermediate"` | `"advanced"`
- `contracts: list[ContractConfig]`
- `templates: list[TemplateConfig]` (advanced only)
- `entity_relationships: list[EntityRelationship]` (advanced only)

**`ContractConfig`** — one contract
- `name`, `address` (validated `0x[a-fA-F0-9]{40}`), `start_block`
- `abi_path` (relative to `abis/`)
- `index_events: bool` (default `True`)
- `call_handlers: list[str]` (intermediate+, e.g. `["transfer(address,uint256)"]`)
- `block_handler: bool` (intermediate+)

**`TemplateConfig`** — dynamic data source / factory pattern (advanced)
- `name`, `abi_path`, `event_handlers: list[str]`
- `source_contract`, `source_event` (which event triggers template instantiation)
- `index_events`, `call_handlers`, `block_handler`

**`EntityRelationship`** (advanced)
- `from_entity`, `to_entity`
- `relation_type`: `"one_to_one"` | `"one_to_many"` | `"many_to_many"`
- `field_name`, `derived_from` (optional)

---

## Complexity levels

| Level | config_version | Features |
|---|---|---|
| basic | 1 | Event indexing only; one entity per contract |
| intermediate | 2 | Events + call handlers + block handlers |
| advanced | 3 | Everything + factory templates + entity relationships |

---

## Generation pipeline (`generate/orchestrator.py`)

Steps in order:
1. Create project directory structure (`abis/`, `src/mappings/`, `generated/`)
2. Load ABIs from paths specified in config
3. Generate `subgraph.yaml` — data sources, handlers, event signatures
4. Generate `schema.graphql` — entities with metadata fields (blockNumber, blockTimestamp, transactionHash)
5. Generate TypeScript mappings — auto (functional) or stub (TODO)
6. Generate `package.json` — AssemblyScript dependencies
7. Generate `README.md` — build/deploy instructions

Supports `--dry-run`: logs what would be written without creating files.

---

## Mapping modes

**Stub** (`mappings_stub.py`) — handler signatures with TODO comments; user fills in logic. Fast starting point for experienced developers.

**Auto** (`mappings_auto.py`) — fully functional handlers that auto-create entities from event parameters, populate metadata fields, and instantiate templates for factory patterns. Works out of the box.

---

## ABI acquisition

Three methods, chosen interactively or via config:
- **Local file** — load from a JSON file on disk
- **Paste** — user pastes JSON at the prompt; collected until `"END"` sentinel line
- **Etherscan** — `GET https://{explorer_host}/api?module=contract&action=getabi&address=...`; API keys from env vars; error messages sanitized to avoid leaking keys

---

## Supported networks (`networks.py`)

| Network | Explorer | Chain ID |
|---|---|---|
| ethereum | api.etherscan.io | 1 |
| optimism | api-optimistic.etherscan.io | 10 |
| arbitrum | api.arbiscan.io | 42161 |

Adding a new network: update `networks.py`, `.env.example`, and `etherscan.py`.

---

## Solidity → GraphQL type mapping (`abi/utils.py`)

| Solidity | GraphQL / AssemblyScript |
|---|---|
| `uint8`–`uint32` | `Int` |
| `uint64`+ | `BigInt` |
| `address` | `Bytes` |
| `bool` | `Boolean` |
| `string` | `String` |
| `bytes`, `bytesN` | `Bytes` |
| `T[]` | `[T!]` |

---

## Generated output structure

```
my-token-subgraph/
├── subgraph.yaml
├── schema.graphql
├── package.json
├── README.md
├── subgraph-config.json         # Saved config for reproducibility
├── abis/
│   └── ContractName.json
└── src/
    └── mappings/
        └── ContractName.ts
```

After generation, user runs: `npm install` → `graph codegen` → `graph build` → deploy.

---

## Environment variables

| Variable | Purpose |
|---|---|
| `ETHERSCAN_API_KEY` | Etherscan API key (ethereum network) |
| `OPTIMISM_ETHERSCAN_API_KEY` | API key for optimism |
| `ARBITRUM_ETHERSCAN_API_KEY` | API key for arbitrum |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`) |
| `DEBUG` | Set to `1` / `true` / `yes` to show full tracebacks |

---

## Error handling

Custom hierarchy in `errors.py`:
- `SubgraphWizardError` (base)
  - `ValidationError` — config/ABI validation failures
  - `AbiFetchError` — explorer API failures

API keys are never logged; error messages are sanitized. Full tracebacks only with `DEBUG=1`.

---

## Validation (`config/validation.py`)

Key checks:
- `network` must be in `SUPPORTED_NETWORKS`
- `address` must match `0x[a-fA-F0-9]{40}`
- Call handler signatures: `functionName(type1,type2,...)`
- Template `source_contract` must reference an existing contract name
- Entity relationship `relation_type` must be valid
- No duplicate contract names or addresses
- Config version compatible with complexity level

---

## Dependencies (`pyproject.toml`)

```
jinja2>=3.1.0
pyyaml>=6.0.0
requests>=2.28.0
```

Dev: `pytest`, `ruff`

Entry point: `subgraph-wizard = subgraph_wizard.main:run`

---

## Testing

```bash
pytest              # all tests
pytest -v           # verbose
pytest --cov        # with coverage
```

21 test files covering:
- `test_cli.py` — arg parsing
- `test_config_io.py` — JSON load/save
- `test_validation.py` — validation rules
- `test_abi_*.py` — all three ABI acquisition methods
- `test_generate_*.py` — individual generator modules
- `test_interactive_wizard*.py` — wizard flow
- `test_full_generation*.py` — end-to-end generation (basic, intermediate, advanced)

Fixtures in `tests/fixtures/`: `basic_config.json`, `advanced_config.json`, sample ABIs (Factory, Pair, SampleToken).

---

## Development notes

- **Branch convention**: `feature/<short-description>`
- **Code style**: PEP 8, type hints throughout, docstrings on all public functions, ruff formatting
- **Commit style**: imperative subject line + bulleted body
- Current milestone: v0.1.0 — manual walkthrough & CI verification complete

---

## Git / deployment

- Remote: `git@github.com:imimim-username/subgraphGenerator.git`
- Branch: `main`
- SSH key for pushing: `REMOVED`
- Push command: `GIT_SSH_COMMAND="ssh -i REMOVED -o StrictHostKeyChecking=no" git push origin main`

---

## Pending / ideas discussed

*(nothing currently open)*

---

## Recent changes

*(no session changes yet — context file created 2026-04-28)*
