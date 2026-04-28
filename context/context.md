# Project Context

## What this is

**Subgraph Wizard** — a Python tool (v0.1.0) that generates ready-to-deploy
subgraph projects for [The Graph](https://thegraph.com/) protocol.

**Three entry points:**

| Mode | Command | Description |
|---|---|---|
| Visual editor | `subgraph-wizard --ui` | Local web UI; drag-and-drop node canvas |
| Interactive wizard | `subgraph-wizard` | Text Q&A flow |
| Config-driven | `subgraph-wizard --config cfg.json --generate` | Non-interactive / CI |

The visual editor is the primary recommended path for new users.

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
│   │   ├── nodes/               # ContractNode, EntityNode, MathNode, TypeCastNode,
│   │   │                        #   StringConcatNode, ConditionalNode, ContractReadNode
│   │   ├── hooks/
│   │   │   └── useValidation.js # Debounced POST /api/validate; returns issue maps
│   │   └── components/
│   │       ├── ValidationPanel.jsx   # Collapsible bottom-left issues list
│   │       ├── NetworksPanel.jsx     # Right-side chain address panel
│   │       └── Toolbar.jsx           # Left-side node palette
│   ├── vite.config.js           # Proxy /api → :8000 in dev; build → static/
│   └── package.json
├── templates/                   # Jinja2 templates (CLI mode)
│   ├── subgraph.yaml.j2
│   ├── README.generated.md.j2
│   ├── package.json.j2
│   ├── schema/
│   └── mappings/
├── tests/
│   ├── fixtures/                # Test configs + sample ABIs
│   ├── test_cli.py
│   ├── test_config_io.py
│   ├── test_validation.py
│   ├── test_abi_*.py
│   ├── test_generate_*.py
│   ├── test_interactive_wizard*.py
│   ├── test_full_generation*.py
│   ├── test_server.py           # FastAPI endpoint tests (31 tests)
│   └── test_validator.py        # Visual graph validator tests (60+ tests)
├── docs/
│   ├── visual-editor-architecture.md  # Visual editor design + implementation
│   ├── architecture.md
│   ├── config-format.md
│   ├── user-guide.md
│   └── development-notes.md
├── examples/
├── pyproject.toml
└── .env.example
```

---

## Visual Editor

### Node types

| Type | File | Description |
|---|---|---|
| `contract` | `ContractNode.jsx` | ABI upload/fetch, event+read ports, multi-instance |
| `entity` | `EntityNode.jsx` | Field ports (input), ID strategy |
| `math` | `MathNode.jsx` | BigInt binary arithmetic |
| `typecast` | `TypeCastNode.jsx` | Type conversion (7 cast modes, `castIndex` 0–6) |
| `strconcat` | `StringConcatNode.jsx` | String concatenation with optional separator |
| `conditional` | `ConditionalNode.jsx` | Boolean guard / early return |
| `contractread` | `ContractReadNode.jsx` | On-chain view function call |

### Key design decisions

- **No separate Event node.** Event parameters are output ports directly on
  the Contract node (e.g. `event-Transfer-from`, `event-Transfer-value`).
- **Networks are a list.** `visual-config.json` stores
  `networks: list[{network, contracts}]`, not a dict.
- **Validation runs live.** `useValidation` debounces 600ms and POSTs to
  `/api/validate` on every canvas change. The **Generate** button is disabled
  while `hasErrors === true`.
- **Save/load via API.** `GET /api/config` loads `visual-config.json` on
  mount; `POST /api/config` saves; `POST /api/generate` writes output files.

### FastAPI endpoints (`server.py`)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/abi/parse` | Parse raw ABI; returns events + read functions |
| `POST` | `/api/abi/fetch` | Fetch ABI from Etherscan; returns abi + events + read functions |
| `GET` | `/api/config` | Load `visual-config.json` (scaffold if missing) |
| `POST` | `/api/config` | Save `visual-config.json`; returns `{saved, path}` |
| `POST` | `/api/validate` | Validate graph; returns `{issues, has_errors}` |
| `POST` | `/api/generate` | Compile + write output files; returns `{files}` |

All endpoints accept `?dir=<path>` to override the working directory.

### Graph validator (`generate/validator.py`)

Error codes (block generation):
- `CONTRACT_NO_NAME`, `CONTRACT_NO_ABI`
- `ENTITY_NO_NAME`, `ENTITY_NO_ID_WIRED`
- `TYPE_MISMATCH`
- `CONTRACTREAD_NO_CONTRACT`, `CONTRACTREAD_BAD_FN_INDEX`

Warning codes (generation continues):
- `CONTRACT_EMPTY_INSTANCE`, `DISCONNECTED_CONTRACT`, `DISCONNECTED_ENTITY`
- `ENTITY_NO_FIELDS`
- `MATH_DISCONNECTED_INPUT` (math nodes), `STRCONCAT_DISCONNECTED` (strconcat nodes)
- `CONDITIONAL_NO_CONDITION`
- `TYPECAST_BAD_INDEX`

### Graph compiler (`generate/graph_compiler.py`)

`compile_graph(visual_config)` → `dict[contract_type, AssemblyScript source]`

Topological traversal: for each event handler, follows edges backward from
Entity field ports through transform nodes (math/typecast/strconcat/conditional/
contractread) to event param ports. Emits variable declarations in dependency
order, then entity load-or-create + field assignments, wrapped in handler
boilerplate.

### `visual-config.json` format

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

### Dev setup

```bash
# Backend (port 8000)
pip install -e .
uvicorn subgraph_wizard.server:app --port 8000 --reload

# Frontend (port 5173, proxies /api → :8000)
cd frontend && npm install && npm run dev
```

### Build for distribution

```bash
cd frontend && npm run build
# outputs to src/subgraph_wizard/static/ (committed to git)
```

---

## CLI / Interactive Wizard

### Interactive wizard

```bash
subgraph-wizard
```

Prompts for: subgraph name, network, contract(s), ABI source, mapping mode.
Produces `subgraph-config.json` and optionally generates immediately.

### Config-driven

```json
{
  "config_version": 1,
  "name": "my-token-subgraph",
  "network": "ethereum",
  "output_dir": "./generated",
  "complexity": "basic",
  "mappings_mode": "auto",
  "contracts": [
    {
      "name": "ERC20",
      "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
      "start_block": 10000000,
      "abi_path": "ERC20.json",
      "index_events": true
    }
  ]
}
```

```bash
subgraph-wizard --config subgraph-config.json --generate
subgraph-wizard --config subgraph-config.json --generate --dry-run
```

---

## Core Data Models (`config/model.py`)

**`SubgraphConfig`** — used by CLI/interactive modes only (not visual editor)
- `name`, `network`, `output_dir`, `mappings_mode` (`"auto"` | `"stub"`)
- `config_version` / `complexity`: `"basic"` | `"intermediate"` | `"advanced"`
- `contracts: list[ContractConfig]`
- `templates: list[TemplateConfig]` (advanced)
- `entity_relationships: list[EntityRelationship]` (advanced)

**`ContractConfig`**
- `name`, `address`, `start_block`, `abi_path`
- `index_events`, `call_handlers`, `block_handler`

The visual editor does **not** use these dataclasses — it works directly with
the JSON `visual-config.json` graph.

---

## Solidity → GraphQL Type Mapping (`abi/utils.py`)

| Solidity | Graph type |
|---|---|
| `uint8`–`uint32` | `Int` |
| `uint64`+ | `BigInt` |
| `address` | `Bytes` |
| `bool` | `Boolean` |
| `string` | `String` |
| `bytes`, `bytesN` | `Bytes` |
| `int8`–`int32` | `Int` |
| `int64`+ | `BigInt` |

---

## Generated Output Structure

**Visual editor mode:**
```
<output-dir>/
├── visual-config.json         ← saved graph state
├── subgraph.yaml              ← mustache-templated
├── networks.json              ← per-chain addresses
└── src/mappings/
    └── {ContractType}.ts      ← compiled AssemblyScript
```

**CLI/interactive mode:**
```
<output-dir>/
├── subgraph.yaml
├── schema.graphql
├── package.json
├── README.md
├── subgraph-config.json
├── abis/
└── src/mappings/
    └── {ContractName}.ts
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

## Dependencies

Runtime (`pyproject.toml`):
```
fastapi>=0.110.0
jinja2>=3.1.0
pyyaml>=6.0.0
requests>=2.28.0
uvicorn>=0.27.0
```

Frontend (`frontend/package.json`): React, @xyflow/react, Tailwind CSS v4,
Vite.

Dev: `pytest`, `ruff`

---

## Testing

```bash
pytest              # all tests
pytest -v
pytest tests/test_validator.py   # validator only
pytest tests/test_server.py      # server/API only
```

Test files of note:
- `test_validator.py` — 60+ tests; covers all 7 node types + type mismatch + issue structure
- `test_server.py` — 31 tests; health, ABI parse/fetch, config CRUD, validate, generate endpoints

---

## Git / Deployment

- Remote: `git@github.com:imimim-username/subgraphGenerator.git`
- Branch: `main`
- SSH key: `REMOVED`
- Push command:
  ```bash
  GIT_SSH_COMMAND="ssh -i REMOVED -o StrictHostKeyChecking=no" git push origin main
  ```

---

## Recent Changes (2026-04-28)

- **M1–M10 complete:** full visual editor implemented and bundled
- **Validator extended:** added `TYPECAST_BAD_INDEX`, `CONDITIONAL_NO_CONDITION`,
  `CONTRACTREAD_NO_CONTRACT`, `CONTRACTREAD_BAD_FN_INDEX`, `STRCONCAT_DISCONNECTED`
  (renamed from `MATH_DISCONNECTED_INPUT` for strconcat nodes)
- **Tests added:** `test_validator.py` and `test_server.py` covering all new functionality
- **Docs rewritten:** `docs/visual-editor-architecture.md` updated to match actual implementation;
  this context file rewritten from scratch to cover both CLI and visual editor modes
