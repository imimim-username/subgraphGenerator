
# Subgraph Wizard – Architecture

This document describes the internal architecture of the **Subgraph Wizard** project:  
how it is structured, how data flows through the system, and where each kind of logic lives.

The goal is to give new contributors (including “future you”) a clear mental model of the system so that:
- You can quickly find where to implement changes.
- You understand how components depend on each other.
- You can extend the tool without breaking existing behavior.

---

## 1. High-Level Overview

**Subgraph Wizard** is a Python-based tool that generates fully structured subgraph projects for The Graph.

There are two main usage modes:

1. **Interactive wizard** – walks the user through questions (network, contracts, ABI, mapping style, etc.)  
2. **Config-driven generation** – reads a `subgraph-config.json` file and generates a subgraph non-interactively.

The output is a subgraph project folder containing:

- `subgraph.yaml`
- `schema.graphql`
- Mapping handlers (`src/mappings/*.ts`)
- `abis/*.json`
- `package.json`
- A generated README for the subgraph

The architecture is organized around the following core concepts:

- **Config model** – how subgraphs are described as data
- **ABI acquisition** – how contract ABIs are obtained
- **Generators** – how config + ABIs are turned into files
- **Templates** – text/graphQL/TypeScript templates used by generators
- **CLI / Wizard** – user interaction and entry points

---

## 2. Project Layout (Reminder)

```text
subgraph-wizard/
├── .env.example
├── src/
│   └── subgraph_wizard/
│       ├── __init__.py
│       ├── main.py
│       ├── cli.py
│       ├── interactive_wizard.py
│       ├── networks.py
│       ├── logging_setup.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── model.py
│       │   ├── io.py
│       │   └── validation.py
│       ├── abi/
│       │   ├── __init__.py
│       │   ├── local.py
│       │   ├── paste.py
│       │   ├── etherscan.py
│       │   └── utils.py
│       ├── generate/
│       │   ├── __init__.py
│       │   ├── orchestrator.py
│       │   ├── project_layout.py
│       │   ├── subgraph_yaml.py
│       │   ├── schema.py
│       │   ├── mappings_stub.py
│       │   ├── mappings_auto.py
│       │   ├── package_json.py
│       │   └── readme.py
│       └── utils/
│           ├── fs_utils.py
│           ├── templating.py
│           └── prompts_utils.py
├── templates/
│   ├── subgraph.yaml.j2
│   ├── README.generated.md.j2
│   ├── package.json.j2
│   ├── schema/
│   │   ├── base_schema.graphql.j2
│   │   ├── auto_entity.graphql.j2
│   │   └── stub_entity.graphql.j2
│   └── mappings/
│       ├── common_header.ts.j2
│       ├── mapping_stub.ts.j2
│       └── mapping_auto.ts.j2
├── examples/
├── docs/
├── tests/
├── pyproject.toml
├── README.md
└── .gitignore
```

---

## 3. Core Data Flow

The core logic follows a simple, repeatable pipeline:

1. **User input → Config**
   - In interactive mode, `interactive_wizard.py` collects answers from the user.
   - In non-interactive mode, `cli.py` loads a pre-existing `subgraph-config.json`.
   - In both cases, the data is represented as a `SubgraphConfig` object (`config/model.py`).

2. **Config → Validation**
   - The config is validated by `config/validation.py`:
     - Networks are checked against `networks.py`.
     - Contract addresses are validated.
     - ABI configuration and mapping modes are checked.
   - Invalid configurations return clear, user-friendly errors.

3. **Config + ABIs → Generation Orchestrator**
   - `generate/orchestrator.py` receives a valid `SubgraphConfig`.
   - It ensures necessary directories exist (`generate/project_layout.py`).
   - It coordinates all generators (schema, mappings, subgraph.yaml, package.json, README).

4. **Generators → Templates → Filesystem**
   - Each generator module reads from:
     - The `SubgraphConfig`
     - ABIs (JSON)
     - Templates in `templates/`
   - `utils/templating.py` renders templates into final files.
   - `utils/fs_utils.py` handles safe writes and directory creation.

The result: a fully formed subgraph project in a target output directory.

---

## 4. Modules and Responsibilities

### 4.1 Entry & Interaction Layer

#### `main.py`
- Provides the top-level entry point.
- Dispatches between:
  - Interactive wizard mode (no `--config` flag).
  - Non-interactive mode (with `--config` and `--generate` flags).

#### `cli.py`
- Parses command-line arguments.
- Supports:
  - `--config path/to/subgraph-config.json`
  - `--generate` to generate files from a config
  - `--dry-run` to preview generation
  - `--version` to show the tool version
- Builds a `SubgraphConfig` by delegating to `config/io.py`.

#### `interactive_wizard.py`
- Implements the question/answer flow in the terminal.
- Collects:
  - Subgraph name, network, and output directory
  - Contracts (name, address, start block)
  - ABI acquisition method (file, paste, Etherscan)
  - Mapping mode (stub vs auto)
  - Complexity level (basic/intermediate/advanced)
- Instantiates a `SubgraphConfig` (without yet writing files).

---

### 4.2 Configuration Layer (`config/`)

#### `config/model.py`
- Defines the core configuration data structures, e.g.:

  - `SubgraphConfig`
  - `ContractConfig`
  - `AbiConfig`
  - `configVersion` for forward compatibility

- Provides typed, structured representations of the config used by all other modules.

#### `config/io.py`
- Responsible for:
  - Serializing `SubgraphConfig` to `subgraph-config.json`.
  - Deserializing JSON back into a `SubgraphConfig`.
- Ensures consistency between interactive and non-interactive modes.

#### `config/validation.py`
- Central validation logic:
  - Network name must be recognized by `networks.py`.
  - Contract addresses must be valid hex strings.
  - ABI configuration must be complete for each contract.
  - Mapping mode and complexity values must be supported.
- Fails fast with meaningful, user-readable error messages.

---

### 4.3 Network Metadata (`networks.py`)

- Stores definitions for supported networks:
  - Identifiers such as `ethereum`, `optimism`, `arbitrum`, etc.
  - Associated explorer API hosts (for Etherscan-compatible endpoints).
  - Optional chain IDs and default addresses/start blocks for templates.
- Used by:
  - ABI fetch via Etherscan.
  - Validation to ensure the chosen network is supported.

---

### 4.4 ABI Acquisition Layer (`abi/`)

#### Goal
Provide a consistent way to obtain ABI JSON regardless of the source.

#### `abi/local.py`
- Loads ABI from user-specified local JSON files.
- Validates that the content is valid JSON before returning.

#### `abi/paste.py`
- Allows the user to paste ABI JSON directly into the terminal.
- Collects lines until a sentinel (e.g., `END`) is entered.
- Parses and validates the JSON content.

#### `abi/etherscan.py`
- Fetches ABI from Etherscan-compatible APIs, optionally using:
  - API keys from environment variables (`.env`).
  - Or API keys entered by the user at runtime.
- Handles:
  - HTTP requests.
  - Explorer-specific responses (e.g., error handling if contract is not verified).
- Ensures API keys are not logged or leaked in error messages.

#### `abi/utils.py`
- Shared helpers for:
  - Parsing ABI arrays.
  - Extracting events, function signatures, and parameter types.
  - Performing any ABI-level validation required by generators.

---

### 4.5 Generation Layer (`generate/`)

The generation layer takes the validated config + ABIs and creates all the files in the subgraph project.

#### `generate/orchestrator.py`
- Orchestrates the full generation pipeline:
  1. Ensures the target output directory and subdirectories exist (`project_layout.py`).
  2. Ensures ABIs are present in the `abis/` folder.
  3. Calls:
     - `subgraph_yaml.py` for `subgraph.yaml`
     - `schema.py` for `schema.graphql`
     - `mappings_stub.py` or `mappings_auto.py` for mapping files
     - `package_json.py` for `package.json`
     - `readme.py` for the subgraph’s own README
- Implements safeguards for overwriting:
  - Optionally requires explicit confirmation or a `--force` flag to overwrite non-empty directories.

#### `generate/project_layout.py`
- Defines the on-disk structure of generated subgraphs:
  - `abis/`
  - `src/mappings/`
  - `generated/` (for `graph codegen` outputs)
- Provides utility functions to construct and verify these directories.

#### `generate/subgraph_yaml.py`
- Converts `SubgraphConfig` (and derived ABI info) into a valid `subgraph.yaml`.
- Handles:
  - Data sources (per contract).
  - Network selection.
  - Mapping file paths.
  - Start blocks.

#### `generate/schema.py`
- Generates the `schema.graphql` file.
- Behavior depends on mapping mode:
  - **Stub mode** – creates minimal or placeholder entities with TODOs.
  - **Auto mode** – generates entities that map directly to event parameters (plus common fields like `blockNumber`, `timestamp`, `txHash`).
- Uses templates in `templates/schema/`.

#### `generate/mappings_stub.py`
- Produces mapping files with:
  - Correct imports.
  - Handler signatures for each selected event.
  - TODO comments showing how to implement entity storage.
- Intended for advanced users who want full control.

#### `generate/mappings_auto.py`
- Produces mapping files that:
  - Instantiate entities per event.
  - Populate entity fields from event parameters.
  - Attach metadata such as block number, timestamp, and transaction hash.
- Designed for fast, beginner-friendly usage.

#### `generate/package_json.py`
- Generates the `package.json` for the subgraph mappings:
  - Dependencies (AssemblyScript, Graph CLI-types, etc.).
  - Scripts if desired (e.g., `codegen`, `build`).

#### `generate/readme.py`
- Generates a folder-specific README for each subgraph:
  - Explains how to install dependencies.
  - Shows how to run `graph codegen`, `graph build`, and deployment commands.
  - Documents what contracts and events are being indexed.

---

### 4.6 Utilities Layer (`utils/`)

#### `utils/fs_utils.py`
- File-system helpers:
  - Creating directories if missing.
  - Safe writing patterns (e.g., write-then-rename).
  - Path normalization.

#### `utils/templating.py`
- Wraps the template engine (e.g., Jinja2).
- Provides functions to render templates from `templates/` with a given context.
- Keeps template rendering concerns separate from generator logic.

#### `utils/prompts_utils.py`
- Standardizes user prompts:
  - Yes/no questions with default options.
  - Choices from a list.
  - Simple validation loops for textual input.

---

## 5. Templates (`templates/`)

The `templates/` directory holds *all text templates* used by the generators.

- `subgraph.yaml.j2`  
  Template for the root `subgraph.yaml`.

- `README.generated.md.j2`  
  Template for the README included with generated subgraphs.

- `package.json.j2`  
  Template for mappings project dependencies and scripts.

- `schema/`  
  - `base_schema.graphql.j2` – Shared base types (if any).  
  - `auto_entity.graphql.j2` – Per-entity template for auto mode.  
  - `stub_entity.graphql.j2` – Minimal entities for stub mode.

- `mappings/`  
  - `common_header.ts.j2` – Shared imports and helper code.  
  - `mapping_stub.ts.j2` – Mapping template for stub handlers.  
  - `mapping_auto.ts.j2` – Mapping template for auto handlers.

Templates are pure text and contain no project logic. All branching, decisions, and data assembly happen in the Python generator modules.

---

## 6. Testing Strategy

The `tests/` directory is intended to cover:

1. **Unit tests** for:
   - Config parsing and validation (`config/io.py`, `config/validation.py`).
   - ABI acquisition modules (`abi/local.py`, `abi/paste.py`, `abi/etherscan.py`).
   - Individual generators (schema, mappings, subgraph.yaml).

2. **Integration / end-to-end tests**:
   - Take a sample `SubgraphConfig` (or JSON file).
   - Run the full generation pipeline into a temporary directory.
   - Compare generated files against “golden” fixture files to ensure stable output.

---

## 7. Environment Variables and Security

The project uses `.env` files for secrets and configuration:

- `.env.example` provides sample keys, e.g.:
  - `ETHERSCAN_API_KEY`
  - `OPTIMISM_ETHERSCAN_API_KEY`
  - `ARBITRUM_ETHERSCAN_API_KEY`
- Users copy `.env.example` → `.env`, which is ignored by Git.

Security guidelines enforced in code:

- API keys are read from environment variables or user input, but never logged.
- Errors from explorer APIs are sanitized to avoid leaking secrets.
- File writes are constrained to intended output directories to reduce path-related issues.

---

## 8. Extension Points

The architecture is designed to make extensions predictable and localized:

- **Add a new network**  
  - Update `networks.py` with network metadata.
  - Optionally add explorer host info for Etherscan-compatible APIs.

- **Add a new ABI source**  
  - Implement a new module under `abi/` (e.g., `subgraph_registry.py`).
  - Wire it into the wizard’s ABI source selection.

- **Add a new mapping style**  
  - Add a new generator module to `generate/` (e.g., `mappings_aggregated.py`).
  - Add templates in `templates/mappings/`.
  - Extend config model and wizard to support the new mode.

- **Add additional complexity modes**  
  - Extend `SubgraphConfig` to describe block handlers, call handlers, or dynamic data sources.
  - Extend the generators to interpret and emit the corresponding `subgraph.yaml` and mapping code.

---

## 9. Design Principles

The architecture is guided by a few core principles:

1. **Single Responsibility**  
   Each module does one thing: configuration, ABI handling, generation, etc.

2. **Separation of Concerns**  
   Business logic is in Python; presentation is in templates; configuration is in JSON.

3. **Config-Driven Behavior**  
   Generators operate solely from configuration models and ABIs. This makes the system predictable and easy to automate.

4. **Extensibility First**  
   New features should require:
   - A new module in the appropriate subpackage.
   - Minimal changes to existing, well-defined interfaces.

5. **Safety & Clarity**  
   The tool avoids dangerous operations, clearly communicates errors, and aims for a beginner-friendly UX.

---

With this architecture in mind, contributors can:

- Quickly locate the correct area to modify.
- Understand how user input becomes a fully generated subgraph.
- Extend the system without introducing cross-cutting, hard-to-debug behavior.
