
# Subgraph Wizard – Development Roadmap & Checklist

This document is a **step-by-step development checklist** for building the Subgraph Wizard tool.

- It assumes the architecture and structure described in `README.md` and `architecture.md`.
- It is organized into **milestones**, each delivering a **thin, working slice**.
- Each milestone contains:
  - Suggested **branch name**
  - Scope
  - Detailed tasks as **checklists**
  - Tests & acceptance criteria
  - Notes on complexity level: **basic → intermediate → advanced**

Developers can work through this in order, opening PRs per milestone (or grouping adjacent ones if appropriate).

---

## Conventions

- **Branch naming**: `feature/<short-description>`  
  e.g. `feature/cli-skeleton`, `feature/basic-generation-auto`.
- **PR titles**: Use imperative, e.g. _"Add basic config model and validation"_.
- **Testing**: Use `pytest` as the primary test runner.
- **Python version**: Target Python **3.10+** (adjust if needed in `pyproject.toml`).
- **Config versioning**: `config_version` is an integer field used to evolve `subgraph-config.json` over time.
- **Error types**: Use a small hierarchy of custom exceptions (see Milestone 1).

---

## Milestone 0 – Repo Initialization & Skeleton

**Goal:** Create a clean, minimal Python project skeleton that matches the high-level architecture, without implementing real logic.

**Branch:** `feature/init-repo-structure`

### Tasks

- [x] Initialize a new Git repository.
- [x] Add a minimal `pyproject.toml` with:
  - [x] Project metadata (name, version `"0.1.0"`, description).
  - [x] `requires-python = ">=3.10"`.
  - [x] Empty `[project.dependencies]` (to be filled later).
  - [x] Placeholder console script:

    ```toml
    [project.scripts]
    subgraph-wizard = "subgraph_wizard.main:run"
    ```

- [x] Create directory layout:

  ```text
  subgraph-wizard/
  ├── src/subgraph_wizard/
  ├── templates/
  ├── docs/
  ├── tests/
  ├── examples/
  ├── .gitignore
  ├── README.md
  └── .env.example
  ```

- [x] Populate `src/subgraph_wizard/` with empty modules (each file just imports `logging` and defines a placeholder docstring):

  - [x] `__init__.py`
  - [x] `main.py`
  - [x] `cli.py`
  - [x] `interactive_wizard.py`
  - [x] `networks.py`
  - [x] `logging_setup.py`
  - [x] `errors.py`
  - [x] `config/__init__.py`, `config/model.py`, `config/io.py`, `config/validation.py`
  - [x] `abi/__init__.py`, `abi/local.py`, `abi/paste.py`, `abi/etherscan.py`, `abi/utils.py`
  - [x] `generate/__init__.py`, `generate/orchestrator.py`, `generate/project_layout.py`, `generate/subgraph_yaml.py`, `generate/schema.py`, `generate/mappings_stub.py`, `generate/mappings_auto.py`, `generate/package_json.py`, `generate/readme.py`
  - [x] `utils/fs_utils.py`, `utils/templating.py`, `utils/prompts_utils.py`

- [x] Add basic `.gitignore` (venv, `__pycache__`, `.env`, `.DS_Store`, etc.).
- [x] Add empty placeholder files in `docs/` and `templates/` (to be fleshed out later).
- [x] Copy in the generated `README.md` and `docs/architecture.md` (or placeholders if not yet committed).

### Tests / Acceptance Criteria

- [x] Add `tests/test_smoke_imports.py` that imports key modules (e.g. `subgraph_wizard.main`) without error.
- [x] `python -m subgraph_wizard` runs without throwing (even if it only prints "Not implemented yet.").

**PR:** _Initialize repository structure and placeholders_

---

## Milestone 1 – Logging, Error Types & CLI Skeleton (Basic)

**Goal:** Provide a working CLI entrypoint with logging and a basic error-handling strategy.

**Branch:** `feature/cli-and-logging-skeleton`

### Tasks

#### 1. Custom Error Types

- [x] Create a new module `src/subgraph_wizard/errors.py` with:

  - [x] `class SubgraphWizardError(Exception): ...`
  - [x] `class ValidationError(SubgraphWizardError): ...`
  - [x] `class AbiFetchError(SubgraphWizardError): ...`
  - [x] (Optional) other specific subclasses as needed later.

#### 2. Logging Setup

- [x] Implement `logging_setup.py`:
  - [x] `setup_logging(level: str = "INFO") -> logging.Logger`.
  - [x] Read `LOG_LEVEL` from environment, fallback to `"INFO"`.
  - [x] Configure a simple console handler.
  - [x] Avoid logging any environment variable whose name contains `"KEY"` or `"TOKEN"` (defensive measure).

#### 3. CLI & Main

- [x] Implement `cli.py` with:

  - [x] `parse_args(argv)` that defines:
    - `--config` (optional path to config JSON).
    - `--generate` (flag).
    - `--dry-run` (flag).
    - `--version` (flag).
  - [x] `run_from_args(args)` that for now:
    - Logs which mode is requested.
    - If `--version`, prints version and returns.

- [x] Implement `main.py`:

  - [x] `run()`:
    - Calls `setup_logging`.
    - Calls `parse_args(sys.argv[1:])`.
    - Wraps `run_from_args(args)` in a `try/except SubgraphWizardError`:
      - On error: print friendly message, exit non-zero, no full traceback unless `DEBUG` env var is set.

### Tests / Acceptance Criteria

- [x] `tests/test_cli.py`:
  - Parse combinations of flags and assert on resulting `Namespace`.
- [x] Manual: `subgraph-wizard --help`, `--version` run without errors.
- [x] Manual: Trigger a synthetic `SubgraphWizardError` in `run_from_args` and verify the CLI shows a clean error message.

**PR:** _Add logging, error hierarchy, and base CLI skeleton_

---

## Milestone 2 – Config Model, IO & Validation (Basic)

**Goal:** Define the `SubgraphConfig` data model, read/write `subgraph-config.json`, and validate it strictly.

**Branch:** `feature/config-model-io-validation`

### Tasks

#### 1. Config Model

- [x] In `config/model.py`, define dataclasses (or Pydantic models if you choose) for:

  - [x] `ContractConfig`:
    - `name: str`
    - `address: str`
    - `start_block: int`
    - `abi_path: str`
    - `index_events: bool = True`

  - [x] `SubgraphConfig`:
    - `config_version: int` (default `1`).
    - `name: str`
    - `network: str`
    - `output_dir: str`
    - `complexity: str` (start with `"basic"` only).
    - `mappings_mode: str` (`"stub"` or `"auto"`).
    - `contracts: list[ContractConfig]`

#### 2. Config IO

- [x] In `config/io.py`:

  - [x] `load_config(path: Path) -> SubgraphConfig`:
    - Read JSON.
    - Validate required fields exist.
    - Construct and return `SubgraphConfig`.

  - [x] `save_config(config: SubgraphConfig, path: Path) -> None`:
    - Serialize to JSON.
    - Include `config_version`.

#### 3. Network Metadata & Validation

- [x] In `networks.py`:

  - [x] Define `SUPPORTED_NETWORKS` mapping, e.g.:

    ```python
    SUPPORTED_NETWORKS = {
        "ethereum": {
            "explorer": "api.etherscan.io",
            "chain_id": 1,
            "default_start_block": 0
        },
        "optimism": {
            "explorer": "api-optimistic.etherscan.io",
            "chain_id": 10,
            "default_start_block": 0
        },
        "arbitrum": {
            "explorer": "api.arbiscan.io",
            "chain_id": 42161,
            "default_start_block": 0
        },
    }
    ```

    Note: `chain_id` and `default_start_block` are optional metadata that may be useful for validation or documentation, but are not strictly required for basic functionality.

- [x] In `config/validation.py`:

  - [x] `validate_config(config: SubgraphConfig) -> None` that:
    - Checks `config.config_version == 1`.
    - Checks `config.network` in `SUPPORTED_NETWORKS`.
    - Validates each `address` as `0x` + 40 hex chars.
    - Ensures `mappings_mode` is `"stub"` or `"auto"`.
    - For now, ensures `complexity == "basic"` (intermediate/advanced to be added later).
    - Raises `ValidationError` on any issue with a clear message.

#### 4. Integrate in CLI

- [x] In `cli.py`, update `run_from_args`:

  - [x] If `--config` is provided:
    - Load config via `load_config`.
    - Call `validate_config`.
    - Log success or raise `ValidationError` on failure.

### Tests / Acceptance Criteria

- [x] `tests/test_config_io.py`:
  - Round-trip: create a `SubgraphConfig` in code → save → load → compare fields.
- [x] `tests/test_validation.py`:
  - Valid config passes.
  - Various invalid configs produce `ValidationError` with expected messages.
- [x] Manual: create a simple `subgraph-config.json` by hand and verify `subgraph-wizard --config <file>` validates it.

**PR:** _Add config model, IO, network metadata, and basic validation_

---

## Milestone 3 – Basic Generation Pipeline (Auto Mode Only)

**Goal:** Implement a minimal generation pipeline for **basic complexity** with **auto mappings only**, from a valid config.

This gives you an MVP: config → generated subgraph with `subgraph.yaml`, `schema.graphql`, one simple mapping.

**Branch:** `feature/basic-generation-auto`

### Tasks

#### 1. FS Utilities & Project Layout

- [x] In `utils/fs_utils.py`:

  - [x] `ensure_dir(path: Path)` – create directory if missing.
  - [x] `safe_write(path: Path, content: str)` – write text safely (temp file → rename).

- [x] In `generate/project_layout.py`:

  - [x] Implement `prepare_project_structure(config: SubgraphConfig) -> dict` returning paths to:
    - `root_dir`
    - `abis_dir`
    - `src_dir`
    - `mappings_dir`

  - [x] Create these directories under `config.output_dir`.

#### 2. Templating Engine

- [x] Add Jinja2 to `pyproject.toml` dependencies.
- [x] In `utils/templating.py`:
  - [x] `get_template_env()` – returns a Jinja2 environment pointing to `templates/`.
    - Template directory should be resolved relative to the package root: `Path(__file__).parent.parent.parent / "templates"`.
  - [x] `render_template(template_name: str, context: dict) -> str`.

#### 3. Minimal Templates

- [x] Create basic versions of:

  - [x] `templates/subgraph.yaml.j2`
  - [x] `templates/schema/base_schema.graphql.j2` (can be empty or minimal)
  - [x] `templates/mappings/common_header.ts.j2`
  - [x] `templates/mappings/mapping_auto.ts.j2` (for a single event/entity to start)

#### 4. Generators (MVP)

- [x] In `generate/subgraph_yaml.py`:
  - [x] Implement `render_subgraph_yaml(config: SubgraphConfig) -> str`:
    - Use a simplified data source model: one mapping file per contract, basic event handler placeholder.

- [x] In `generate/schema.py`:
  - [x] Implement a **very basic** auto schema:
    - For now, you can define a single `ExampleEntity` with fixed fields as a placeholder (will be replaced later once ABI logic is connected).

- [x] In `generate/mappings_auto.py`:
  - [x] Implement generation of a single trivial mapping file per contract:
    - Use `common_header.ts.j2` + `mapping_auto.ts.j2`.
    - For now, the handler can just log or set a minimal placeholder (e.g., using a dummy event type); this will be improved once ABI is wired in.

- [x] In `generate/orchestrator.py`:
  - [x] Implement `generate_subgraph_project(config: SubgraphConfig, dry_run: bool = False)`:
    - Prepare project layout.
    - Render `subgraph.yaml`, `schema.graphql`, and basic mapping files.
    - If `dry_run`, log what would be written instead of writing:
      - For each file, log: file path, file size (in bytes), and a preview of first ~200 characters.
      - Use a consistent log format like: `[DRY RUN] Would write: <path> (<size> bytes)`.

#### 5. CLI Integration

- [x] In `cli.py`:
  - [x] On `--generate`:
    - Load + validate config.
    - Call `generate_subgraph_project(config, dry_run=args.dry_run)`.

### Tests / Acceptance Criteria

- [x] `tests/test_generate_project_layout.py`:
  - Ensures directories are created correctly.
- [x] `tests/test_generate_subgraph_yaml.py`:
  - For a sample config, check YAML contains correct network and contract names.
- [x] `tests/test_basic_generation_flow.py`:
  - Use a sample `SubgraphConfig` in code.
  - Generate into a temp directory.
  - Assert that `subgraph.yaml`, `schema.graphql`, and at least one mapping file exist.

**PR:** _Implement basic generation pipeline for auto mode MVP_

---

## Milestone 4 – ABI Acquisition (File & Paste) and Auto Schema

**Goal:** Connect ABIs to the generation pipeline for **basic complexity**, still focusing on **auto mode**, using local and pasted ABIs.

**Branch:** `feature/abi-file-paste-auto-schema`

### Tasks

#### 1. ABI Utilities

- [x] In `abi/utils.py`:
  - [x] Functions to:
    - Parse ABI JSON (list[dict]).
    - Extract events and their parameters.
    - Map Solidity types to Graph/AssemblyScript types.

#### 2. ABI Sources: Local & Paste

- [x] In `abi/local.py`:
  - [x] `load_abi_from_file(path: Path) -> list[dict]`.

- [x] In `abi/paste.py`:
  - [x] `load_abi_from_paste(text: str) -> list[dict]`.
  - [x] Implement a multi-line paste mechanism:
    - Prompt user to paste ABI JSON (can be formatted across multiple lines).
    - Accept input until user enters `END` on a new line, or handle EOF (Ctrl+D / Ctrl+Z).
    - Parse the collected text as JSON and validate it's a valid ABI array.

#### 3. Auto Schema with Real ABIs

- [x] Update `generate/schema.py`:
  - [x] Accept a mapping of `contract_name -> ABI`.
  - [x] For **auto mode**:
    - Generate one entity type per event, e.g. `EventName`.
    - Include fields for event params + metadata (block number, timestamp, tx hash).

- [x] Update `generate/mappings_auto.py`:
  - [x] Generate a handler per event that:
    - Creates `EventName` entity.
    - Copies parameters into fields.
    - Sets metadata fields.

#### 4. Orchestrator ABI Integration

- [x] In `generate/orchestrator.py`:
  - [x] For each `ContractConfig`:
    - Load ABI from `config.output_dir / "abis" / abi_path`.
    - Note: `abi_path` in `ContractConfig` should be just the filename (e.g., `"MyContract.json"`), not a full path.
    - Build `abi_map` for schema & mappings.

### Tests / Acceptance Criteria

- [x] `tests/test_abi_sources.py`:
  - Local: good/bad file JSON.
  - Paste: good/bad JSON.
- [x] `tests/test_generate_schema_auto_with_abi.py`:
  - Given a minimal ABI with one event, assert:
    - Generated schema contains `type EventName`.
    - Fields match event parameters.
- [x] `tests/test_generate_mappings_auto_with_abi.py`:
  - Check mapping contains a handler for the event, uses correct types and entity name.

**PR:** _Wire ABI from file/paste into auto schema and mappings for basic subgraphs_

---

## Milestone 5 – Etherscan/Explorer ABI Fetch (Basic)

**Goal:** Add an optional ABI source from Etherscan-compatible explorers for basic complexity / auto mode.

**Branch:** `feature/abi-etherscan-basic`

### Tasks

- [x] Update `.env.example`:

  - [x] Add:
    - `ETHERSCAN_API_KEY=`
    - `OPTIMISM_ETHERSCAN_API_KEY=`
    - `ARBITRUM_ETHERSCAN_API_KEY=`

- [x] In `abi/etherscan.py`:

  - [x] Implement `fetch_abi_from_explorer(network: str, address: str) -> list[dict]`:
    - Use `SUPPORTED_NETWORKS[network]["explorer"]`.
    - Read relevant API key from environment.
    - Use short timeouts (e.g., 10 seconds).
    - On error (rate limit, unverified contract, network issues), raise `AbiFetchError` with a **sanitized** message:
      - Do NOT include API key in error messages.
      - Do NOT include full URLs with query parameters in error messages.
      - Provide user-friendly messages like: "Failed to fetch ABI from explorer. Contract may not be verified, or API rate limit exceeded. Please check your API key or try using a local ABI file."
      - Optionally log detailed error info at DEBUG level (with sanitization).

- [x] Provide a helper function that can be called later by the wizard.

### Tests / Acceptance Criteria

- [x] `tests/test_abi_etherscan.py`:
  - Use `unittest.mock` or similar to mock `requests.get`.
  - Test success path (valid ABI JSON string in `result`).
  - Test error path (status `"0"` with error message).

**PR:** _Add Etherscan-compatible ABI fetch support for basic mode_

---

## Milestone 6 – Interactive Wizard (Basic Config + ABI Choice)

**Goal:** Implement the interactive wizard for **basic complexity**, letting the user define contracts and choose ABI sources (file, paste, Etherscan).

**Branch:** `feature/interactive-wizard-basic`

### Tasks

- [x] In `utils/prompts_utils.py`:
  - [x] Implement helper functions:
    - `ask_string(prompt, default=None)`
    - `ask_choice(prompt, options: list[str], default_index=0)`
    - `ask_yes_no(prompt, default=True)`

- [x] In `interactive_wizard.py`:
  - [x] Implement `run_wizard() -> SubgraphConfig`:
    - Ask for:
      - Subgraph name.
      - Network (from `SUPPORTED_NETWORKS`).
      - Output directory (default = name).
      - Complexity (for now, **force `basic`** – record it explicitly).
      - Mapping mode (`stub` vs `auto`):
        - Note: Stub mode implementation begins in Milestone 7. If user selects `stub` in Milestone 6, allow the selection and save it in config, but warn: "Stub mappings will be generated in a future milestone. For now, only auto mode is fully functional."
    - Contract entry loop:
      - For each contract:
        - Name, address, start block.
        - ABI source:
          - 1) Local file
          - 2) Paste JSON (multi-line until `END` or EOF)
          - 3) Fetch from explorer
        - Use appropriate `abi/` module.
        - Write ABI to `output_dir/abis/<ContractName>.json`.
        - Set `abi_path` in `ContractConfig` to just the filename: `"<ContractName>.json"` (relative to `abis/` directory).
    - Build `SubgraphConfig`.
    - Call `validate_config`.
    - Save to `<output_dir>/subgraph-config.json`.

- [x] In `main.run()` / `cli.run_from_args()`:
  - [x] If no `--config` and no `--generate`, run the wizard and then optionally ask the user if they want to generate immediately.

### Tests / Acceptance Criteria

- [x] `tests/test_interactive_wizard_basic.py`:
  - Use `monkeypatch` to simulate input and `tmp_path` for `output_dir`.
  - Assert a `SubgraphConfig` is built and saved.
  - Assert ABI files are written.

**PR:** _Add interactive wizard for basic complexity and ABI acquisition_

---

## Milestone 7 – Stub Mappings, Package.json, and Generated README (Basic)

**Goal:** Complete the **basic complexity** feature set by adding stub mappings, `package.json`, and per-subgraph README.

**Branch:** `feature/basic-stub-mappings-and-metadata`

### Tasks

#### 1. Stub Mappings

- [x] In `templates/mappings/mapping_stub.ts.j2`:
  - [x] Create a template that:
    - Imports event types.
    - Declares handler functions with TODO comments.

- [x] In `generate/mappings_stub.py`:
  - [x] Given ABI info, generate stubs for each event.
  - [x] Ensure naming conventions match `schema.graphql` types (even if stubbed).

#### 2. Package.json

- [x] In `templates/package.json.j2`:
  - [x] Fill in typical subgraph/mappings dependencies and scripts (`codegen`, `build`):
    - Required dependencies:
      - `@graphprotocol/graph-cli`: latest stable version
      - `@graphprotocol/graph-ts`: latest stable version
    - Scripts:
      - `codegen`: `graph codegen`
      - `build`: `graph build`
      - `deploy`: `graph deploy --node <node-url> <subgraph-name>` (placeholder, user should customize)

- [x] In `generate/package_json.py`:
  - [x] Render `package.json` using config data where appropriate (e.g., name).

#### 3. Generated Subgraph README

- [x] In `templates/README.generated.md.j2`:
  - [x] A template explaining:
    - Network.
    - Contracts.
    - How to install dependencies.
    - Commands to run `graph codegen` and `graph build`.

- [x] In `generate/readme.py`:
  - [x] Render this template for each generated subgraph.

#### 4. Orchestrator Integration

- [x] Update `generate/orchestrator.py`:
  - [x] If `mappings_mode == "stub"`, use stub generator.
  - [x] Generate `package.json` and README in all cases.

### Tests / Acceptance Criteria

- [x] `tests/test_generate_mappings_stub.py`:
  - Check that stub handlers exist for expected events and contain TODO comments.
- [x] `tests/test_generate_package_json.py`:
  - Load `package.json` and assert required fields and dependencies.
- [x] `tests/test_generate_readme.py`:
  - Assert network and contract names appear in generated README.

**PR:** _Add stub mappings, package.json, and generated subgraph README for basic complexity_

---

## Milestone 8 – End-to-End Basic Mode & Semantic Tests

**Goal:** Validate the **full basic pipeline** (config → wizard → generate → subgraph) with robust tests.

**Branch:** `feature/basic-end-to-end-tests`

### Tasks

- [x] Add `tests/fixtures/basic_config.json` and sample ABI(s).
- [x] In `tests/test_full_generation_basic.py`:
  - [x] Load fixture config.
  - [x] Run `generate_subgraph_project` into a temp directory.
  - [x] Assertions:
    - Check that key files exist (`subgraph.yaml`, `schema.graphql`, mappings, `package.json`, README).
    - For `subgraph.yaml`, parse YAML and assert:
      - Correct network.
      - Correct dataSources.
    - For `schema.graphql`, parse as text and assert presence of known entity names and fields (not full byte-by-byte match).
    - For mappings, assert presence of key function names and types.

- [ ] Manually run the tool:
  - [ ] `subgraph-wizard` → use wizard to create a basic config and generate a subgraph.
  - [ ] Validate with `graph codegen` and `graph build` (if Graph CLI is installed).

**PR:** _Add end-to-end generation tests for basic complexity_

---

## Milestone 9 – Introduce “Intermediate” Complexity

**Goal:** Extend the config and generation pipeline to support **intermediate complexity** (e.g., call handlers and/or block handlers), without breaking basic behavior.

**Branch:** `feature/intermediate-complexity-support`

### Tasks

#### 1. Config Extensions

- [x] In `config/model.py`:
  - [x] Extend `ContractConfig` with optional fields for intermediate complexity:
    - `call_handlers: list[str] | None = None` – list of function signatures or names to index (e.g., `["transfer(address,uint256)"]`).
    - `block_handler: bool = False` – whether to index every block for this contract.
  - [x] Extend `SubgraphConfig` with optional intermediate complexity fields:
    - Fields can be added at the top level or within `ContractConfig` (recommended: within `ContractConfig`).
  - [x] Bump `config_version` to `2` for new configs created with intermediate features.
  - [x] Config versioning strategy:
    - Implement backward compatibility: accept both version 1 and version 2 configs in `config/validation.py`.
    - When loading version 1 configs, initialize intermediate fields with defaults (empty lists, `False`).
    - No automatic migration needed initially; version 1 configs remain valid and functional.

- [x] In `config/validation.py`:
  - [x] Validate intermediate-only fields only when `complexity == "intermediate"`.

#### 2. Wizard Updates

- [x] In `interactive_wizard.py`:
  - [x] Allow user to choose `complexity = "basic" | "intermediate"`.
  - [x] If `intermediate`:
    - For each contract:
      - Ask whether to enable call handlers: `ask_yes_no("Enable call handlers for this contract?")`.
        - If yes, prompt for function signatures (comma-separated or one per line until empty line).
        - Store as list in `ContractConfig.call_handlers`.
      - Ask whether to enable block handlers: `ask_yes_no("Enable block handlers for this contract?")`.
        - Store as boolean in `ContractConfig.block_handler`.
    - Populate intermediate-specific config fields in each `ContractConfig`.

#### 3. Generators

- [x] In `generate/subgraph_yaml.py`:
  - [x] Use intermediate fields to:
    - Add `callHandlers` and/or `blockHandlers` entries under relevant dataSources.

- [x] In mapping generators:
  - [x] Generate stub or auto handlers (depending on `mappings_mode`) for these call/block handlers.
  - [x] For intermediate, it's fine if logic is largely stubbed with TODOs initially.

### Tests / Acceptance Criteria

- [x] Extend `tests/test_validation.py` for intermediate fields.
- [x] `tests/test_generate_subgraph_yaml_intermediate.py`:
  - Assert that `callHandlers` or `blockHandlers` appear in `subgraph.yaml` when expected.
- [x] Ensure all basic tests (Milestones 0–8) still pass.

**PR:** _Add intermediate complexity support for call/block handlers_

---

## Milestone 10 – Introduce “Advanced” Complexity

**Goal:** Add **advanced complexity**, such as dynamic data sources, templates, and multi-contract relationships, while preserving basic & intermediate flows.

**Branch:** `feature/advanced-complexity-support`

### Tasks

This milestone is intentionally more flexible and should be guided by your real advanced use cases.

- [x] Extend `SubgraphConfig` to model advanced concepts:
  - Dynamic data sources and templates.
  - Potential relationships between entities and multiple contracts.
- [x] Extend wizard to:
  - Offer `complexity = "advanced"`.
  - Collect required advanced options in a manageable way.

- [x] Extend generators:
  - `generate/subgraph_yaml.py`:
    - Add `templates` and `dynamicDataSources` sections.
  - Mapping generators:
    - Add mapping code needed to instantiate and manage dynamic data sources.

- [x] Update docs:
  - [x] `docs/config-format.md` – advanced fields.
  - [x] `docs/user-guide.md` – examples of advanced configs.

### Tests / Acceptance Criteria

- [x] Add advanced fixtures in `tests/fixtures/`.
- [x] Add `tests/test_generate_subgraph_yaml_advanced.py` and similar mapping tests.
- [x] Add an advanced end-to-end test (semantic checks only, as with basic and intermediate).

**PR:** _Add advanced complexity, templates, and dynamic data source support_

---

## Milestone 11 – Documentation & Polish

**Goal:** Make sure the implementation fully aligns with `README.md`, `architecture.md`, and provides a smooth developer/user experience.

**Branch:** `feature/docs-and-polish`

### Tasks

- [x] Update `README.md`:
  - [x] Add “Quickstart” section (install, basic example).
  - [x] Show both interactive wizard and config-driven workflows.
- [x] Update `docs/architecture.md` if anything changed vs original plan.
- [x] Flesh out:
  - [x] `docs/user-guide.md` – detailed usage.
  - [x] `docs/config-format.md` – config schema for all complexity levels.
  - [x] `docs/development-notes.md` – contributing guidelines, branch/PR conventions, how to run tests/CI.

- [x] Confirm `.env.example` contains all relevant env vars actually used in code.
- [ ] Optionally add CI configuration (e.g., GitHub Actions) to:
  - Run `pytest`.
  - (Optionally) run linting/formatting.

### Tests / Acceptance Criteria

- [ ] Manual walkthrough:
  - Fresh clone of repo.
  - Follow `README` Quickstart end-to-end.
  - Confirm all steps work.
- [ ] CI passes (if configured).

**PR:** _Align documentation, examples, and polish with the final implementation_

---

## How to Use This Checklist

- Treat each **milestone** as a high-level goal with one or more PRs.
- Ensure each PR delivers a **testable slice**:
  - New code.
  - New or updated tests.
  - Clear acceptance criteria met.
- Regularly compare the current implementation against:
  - `README.md`
  - `docs/architecture.md`
- Adjust future milestones if real-world needs evolve, while keeping the same overall structure and quality goals.

By following this roadmap, you should end up with a **robust, well-architected Subgraph Wizard** that supports:

- **Basic** subgraphs (events → entities, auto/stub).
- **Intermediate** features (call/block handlers).
- **Advanced** features (dynamic data sources, templates, relationships),

with a clean internal design, strong tests, and professional documentation.
