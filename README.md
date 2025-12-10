
# Subgraph Wizard

A modular, extensible Python-based tool that interactively generates ready‑to‑deploy subgraph projects for The Graph.  
The wizard asks users questions (contracts, networks, ABIs, mapping style, etc.) and outputs a complete subgraph folder  
containing `subgraph.yaml`, schema files, mapping handlers, ABIs, and build instructions.

This repository is structured with clear separation of concerns and is designed so contributors can easily locate  
and modify individual components. Each major functional area lives in its own directory or module for maximum clarity,  
maintainability, and extensibility.

---

## 📁 Project Structure Overview

```
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
│   ├── basic-single-contract/
│   └── multi-contract-advanced/
├── docs/
│   ├── architecture.md
│   ├── config-format.md
│   ├── user-guide.md
│   └── development-notes.md
├── tests/
│   ├── test_cli.py
│   ├── test_interactive_wizard.py
│   ├── test_config_io.py
│   ├── test_validation.py
│   ├── test_abi_sources.py
│   ├── test_generate_subgraph_yaml.py
│   ├── test_generate_schema.py
│   ├── test_generate_mappings_stub.py
│   ├── test_generate_mappings_auto.py
│   └── test_full_generation_flow.py
├── pyproject.toml
├── README.md
└── .gitignore
```

---

## 🌱 What This Project Does

The **Subgraph Wizard** helps users create subgraph projects with little or no prior The Graph development experience.

It provides:

- An **interactive wizard** for guided creation  
- A **non-interactive mode** using a `subgraph-config.json` config file  
- Support for ABI input via:
  - Local file  
  - Pasted JSON  
  - Etherscan-compatible explorers  
- Options for:
  - **Stub mappings** (with TODOs)  
  - **Auto-generated mappings** (fully functional handlers)  
- Automatic writing of:
  - `schema.graphql`  
  - `subgraph.yaml`  
  - Mapping files  
  - `package.json`  
  - A generated README explaining how to build/deploy the subgraph  

The generated output is a complete subgraph that can be immediately built using:

```
graph codegen
graph build
```

---

## 🚀 Quickstart

### Installation

**Prerequisites:**
- Python 3.10 or higher
- pip (Python package manager)

**Install from source:**

```bash
# Clone the repository
git clone <repository-url>
cd subgraph-wizard

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .

# Verify installation
subgraph-wizard --version
```

### Example 1: Interactive Wizard

The easiest way to create a subgraph is using the interactive wizard:

```bash
subgraph-wizard
```

The wizard will guide you through:
1. Subgraph name (e.g., `my-token-subgraph`)
2. Network selection (e.g., `ethereum`, `optimism`, `arbitrum`)
3. Contract configuration (name, address, start block)
4. ABI acquisition method:
   - Local file path
   - Paste JSON directly
   - Fetch from Etherscan/explorer API
5. Mapping mode (`stub` or `auto`)
6. Complexity level (`basic`, `intermediate`, or `advanced`)

After completing the wizard, it will save a `subgraph-config.json` file and optionally generate the subgraph immediately.

**Example workflow:**
```bash
$ subgraph-wizard
Subgraph Wizard starting...
Enter subgraph name: my-token-subgraph
Select network: ethereum
Enter contract name: TestToken
Enter contract address: 0x6B175474E89094C44Da98b954EedeAC495271d0F
Enter start block: 12345678
Select ABI source: [1] Local file [2] Paste JSON [3] Fetch from explorer
...
Configuration saved to: ./my-token-subgraph/subgraph-config.json
Generate subgraph now? [Y/n]: y
Generating subgraph...
✓ Subgraph generated successfully!
```

### Example 2: Config-Driven Workflow

For non-interactive usage or automation, create a `subgraph-config.json` file:

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

Then generate the subgraph:

```bash
# Generate from config
subgraph-wizard --config subgraph-config.json --generate

# Or preview without writing files
subgraph-wizard --config subgraph-config.json --generate --dry-run
```

**Note:** Make sure the ABI file (`TestToken.json` in this example) exists in the `abis/` directory relative to your config file, or use the interactive wizard first to set up the ABI files.

### Next Steps

After generation, build and deploy your subgraph:

```bash
cd <output_dir>
npm install
graph codegen
graph build
graph deploy --node <node-url> <subgraph-name>
```

For more detailed documentation, see:
- [User Guide](docs/user-guide.md) – Complete usage instructions
- [Config Format](docs/config-format.md) – Configuration file reference
- [Architecture](docs/architecture.md) – System design overview

---

## 🔑 Environment Variables (`.env.example`)

Users copy `.env.example` → `.env`.  
`.env` is automatically ignored via `.gitignore` to protect secrets.

Example:

```
# Explorer API Keys
ETHERSCAN_API_KEY=
OPTIMISM_ETHERSCAN_API_KEY=
ARBITRUM_ETHERSCAN_API_KEY=

# Optional logging overrides
LOG_LEVEL=INFO
```

These values are used when the user chooses “Fetch ABI from Etherscan/Explorer API”.

---

## 🧩 Detailed Description of Each Component

### Top-level files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Defines dependencies, entry points (`subgraph-wizard` command), and packaging. |
| `README.md` | Main documentation explaining how the tool works. |
| `.env.example` | Template environment variables for explorers and configuration. |
| `.gitignore` | Ensures `.env`, build artifacts, and generated subgraphs are not committed. |

---

## 📦 `src/subgraph_wizard/` — Core Package

### `main.py`
Entry point for CLI execution (`python -m subgraph_wizard`). Delegates to interactive or CLI mode.

### `cli.py`
Parses command-line flags for non-interactive usage:
- `--config subgraph-config.json`
- `--generate`
- `--dry-run`

### `interactive_wizard.py`
Implements the guided Q&A wizard:
- Subgraph name  
- Network selection  
- Contract list  
- ABI ingestion method  
- Mapping mode  
- Output directory  
Produces a structured `SubgraphConfig` object.

### `networks.py`
Defines supported networks and their explorer settings, like:
- API host  
- Chain IDs  
- Default start blocks  

### `logging_setup.py`
Centralizes logging format, log levels, output coloring, etc.

---

## 🗂 `config/` — Configuration Logic

### `model.py`
Defines the config schema using data classes:
- `SubgraphConfig`
- `ContractConfig`  
- `configVersion`

### `io.py`
Handles reading/writing:
- `subgraph-config.json`
- Validation before saving

### `validation.py`
Strict validation:
- Network names  
- Contract addresses  
- ABI shape correctness  
- Mapping mode legality  

Provides clear error messages.

---

## 🧬 `abi/` — ABI Input Methods

### `local.py`
Loads ABI from a local JSON file.

### `paste.py`
Allows pasting ABI JSON directly into the wizard.

### `etherscan.py`
Fetches ABI via Etherscan-like APIs using environment variables or user prompts.

### `utils.py`
Shared helpers to:
- Parse ABIs  
- Extract event signatures  
- Validate structure  

---

## 🏗 `generate/` — Subgraph File Generators

Each module handles one part of the generated output.

### `orchestrator.py`
The central dispatcher:
1. Creates directory layout  
2. Writes ABI files  
3. Generates schema, mappings, subgraph.yaml  
4. Writes project README and package.json  

### `project_layout.py`
Creates folder structure:

```
subgraph/
├── abis/
├── src/
│   └── mappings/
└── generated/
```

### `subgraph_yaml.py`
Converts config into a valid `subgraph.yaml`.

### `schema.py`
Generates `schema.graphql`:
- Stub mode → minimal entities  
- Auto mode → event-based entities  

### `mappings_stub.py`
Produces handler files containing TODO logic.

### `mappings_auto.py`
Generates fully functional handlers that:
- Create entities per event  
- Save event parameters automatically  

### `package_json.py`
Defines dependencies needed for AssemblyScript mappings.

### `readme.py`
Creates a README specific to the generated subgraph.

---

## 🛠 `utils/` — General Helper Utilities

### `fs_utils.py`
Safe file I/O, directory creation, path normalization.

### `templating.py`
Jinja2 wrapper for rendering templates with runtime values.

### `prompts_utils.py`
Reusable prompt logic:
- yes/no helpers  
- selecting from lists  
- default values  

---

## 🧪 Tests

A mix of unit and integration tests ensures the generator behaves consistently.

Key test categories:
- CLI tests
- Wizard logic tests
- ABI ingestion tests
- Schema/mapping/subgraph.yaml generation
- End‑to‑end generation tests comparing output to golden files

---

## 📖 Docs

### `architecture.md`
High-level system design describing major modules and data flows.

### `user-guide.md`
How to:
- Install  
- Run wizard  
- Provide ABIs  
- Generate subgraphs  

### `config-format.md`
Formal description of `subgraph-config.json`.

### `development-notes.md`
Information for contributors:
- Adding networks  
- Adding new mapping modes  
- Template guidelines  

---

## 🤝 Contributing

This project is structured for contributors to jump in easily.  
Each logical area has its own module, and the README explains where everything lives.

If you want to extend the project:
- Add new networks: edit `networks.py`  
- Add new ABI ingestion methods: extend `abi/`  
- Add new mapping styles: extend `generate/mappings_*.py`  
- Add new templates: modify `templates/`  

---

## 📬 Feedback

Please open issues or PRs for:
- Better mappings
- Support for more networks
- Additional complexity modes
- Improved UX for the wizard  

Happy building!
