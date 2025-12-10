# Subgraph Wizard – Development Notes

This document provides guidelines for contributors to the Subgraph Wizard project. It covers development setup, testing, code conventions, and how to extend the system.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Conventions](#code-conventions)
- [Branch and PR Conventions](#branch-and-pr-conventions)
- [Extension Points](#extension-points)
- [CI/CD](#cicd)
- [Debugging Tips](#debugging-tips)

---

## Development Setup

### Prerequisites

- **Python 3.10 or higher** (check with `python --version`)
- **pip** (Python package manager)
- **Git** for version control

### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd subgraph-wizard
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the package in development mode**:
   ```bash
   pip install -e .
   ```

   This installs the package in "editable" mode, so changes to source code are immediately reflected without reinstalling.

4. **Install development dependencies** (if any):
   ```bash
   # Currently, all dependencies are in pyproject.toml
   # If you add dev dependencies, install them here
   pip install pytest pytest-cov  # Example: if you want coverage
   ```

5. **Set up environment variables** (optional, for testing Etherscan integration):
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys if testing Etherscan functionality
   ```

### Verify Installation

```bash
# Check that the CLI command works
subgraph-wizard --version

# Verify imports work
python -c "import subgraph_wizard; print('OK')"
```

---

## Running Tests

The project uses **pytest** as the test runner. Tests are located in the `tests/` directory.

### Running All Tests

```bash
# From the project root
pytest

# Or with verbose output
pytest -v

# Or with even more detail
pytest -vv
```

### Running Specific Tests

```bash
# Run a specific test file
pytest tests/test_cli.py

# Run a specific test class
pytest tests/test_cli.py::TestParseArgs

# Run a specific test function
pytest tests/test_cli.py::TestParseArgs::test_parse_args_no_flags
```

### Running Tests with Coverage

```bash
# Install coverage tool first (if not already installed)
pip install pytest-cov

# Run tests with coverage report
pytest --cov=subgraph_wizard --cov-report=html

# View HTML report
open htmlcov/index.html  # On macOS/Linux
# or
start htmlcov/index.html  # On Windows
```

### Test Structure

Tests follow pytest conventions:
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

Example test structure:
```python
def test_something():
    """Test description."""
    # Arrange
    value = 42
    
    # Act
    result = function_under_test(value)
    
    # Assert
    assert result == expected_value
```

### Test Fixtures

Test fixtures are located in `tests/fixtures/`:
- `basic_config.json` – Example basic complexity config
- `advanced_config.json` – Example advanced complexity config
- `*.json` – Sample ABI files for testing

---

## Code Conventions

### Python Style

- Follow **PEP 8** style guidelines
- Use **type hints** where appropriate
- Write **docstrings** for all public functions and classes
- Keep functions focused and small (single responsibility)

### Module Organization

- Each major feature area has its own module/package
- Keep business logic separate from I/O operations
- Use dataclasses for configuration models
- Keep templates pure (no logic in Jinja2 templates)

### Error Handling

- Use custom exception hierarchy from `errors.py`:
  - `SubgraphWizardError` – Base exception
  - `ValidationError` – Configuration validation errors
  - `AbiFetchError` – ABI acquisition errors
- Always provide clear, user-friendly error messages
- Never log or expose API keys or secrets

### Logging

- Use the logging module (not `print()`)
- Set up logging via `logging_setup.py`
- Use appropriate log levels:
  - `DEBUG` – Detailed diagnostic information
  - `INFO` – General informational messages
  - `WARNING` – Warning messages
  - `ERROR` – Error messages
- Never log secrets (API keys, tokens, etc.)

Example:
```python
import logging

logger = logging.getLogger(__name__)

def my_function():
    logger.debug("Detailed debug info")
    logger.info("Operation completed")
    logger.warning("Something unusual happened")
    logger.error("An error occurred")
```

---

## Branch and PR Conventions

### Branch Naming

Use the pattern: `feature/<short-description>`

Examples:
- `feature/cli-skeleton`
- `feature/basic-generation-auto`
- `feature/intermediate-complexity-support`
- `feature/docs-and-polish`

### Creating a Branch

```bash
# Start from main (or the base branch)
git checkout main
git pull origin main

# Create and switch to new branch
git checkout -b feature/my-new-feature
```

### Commit Messages

Write clear, descriptive commit messages:

```
Add basic config model and validation

- Implement SubgraphConfig and ContractConfig dataclasses
- Add config validation for networks and addresses
- Include unit tests for validation logic
```

### Pull Request Guidelines

1. **PR Title**: Use imperative mood, e.g., "Add basic config model and validation"
2. **PR Description**: Include:
   - What changes were made
   - Why the changes were needed
   - How to test the changes
   - Any breaking changes
3. **Link to Issues**: Reference related issues if applicable
4. **Tests**: Ensure all tests pass before submitting
5. **Documentation**: Update relevant docs if behavior changes

### PR Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Write/update tests
4. Ensure all tests pass: `pytest`
5. Update documentation if needed
6. Commit your changes
7. Push to your fork
8. Open a PR against `main`
9. Address review feedback
10. Once approved, maintainers will merge

---

## Extension Points

The architecture is designed to make extensions predictable and localized. Here's how to add common features:

### Adding a New Network

1. **Update `networks.py`**:
   ```python
   SUPPORTED_NETWORKS = {
       # ... existing networks ...
       "polygon": {
           "explorer": "api.polygonscan.com",
           "chain_id": 137,
           "default_start_block": 0
       },
   }
   ```

2. **Update `.env.example`** (if using Etherscan-compatible API):
   ```
   POLYGON_ETHERSCAN_API_KEY=
   ```

3. **Update `abi/etherscan.py`** (if needed):
   ```python
   NETWORK_API_KEY_ENV_VARS = {
       # ... existing mappings ...
       "polygon": "POLYGON_ETHERSCAN_API_KEY",
   }
   ```

4. **Add tests** in `tests/test_validation.py` to verify the new network is accepted

### Adding a New ABI Source

1. **Create a new module** in `abi/` (e.g., `abi/subgraph_registry.py`):
   ```python
   """Fetch ABI from a subgraph registry."""
   
   from subgraph_wizard.errors import AbiFetchError
   
   def fetch_abi_from_registry(registry_url: str, contract_address: str) -> list[dict]:
       """Fetch ABI from a subgraph registry."""
       # Implementation here
       pass
   ```

2. **Wire it into the wizard** in `interactive_wizard.py`:
   - Add it as an option in the ABI source selection
   - Call the new function when selected

3. **Add tests** in `tests/test_abi_sources.py`

### Adding a New Mapping Style

1. **Create a new generator** in `generate/` (e.g., `generate/mappings_aggregated.py`):
   ```python
   """Generate aggregated mapping handlers."""
   
   def generate_aggregated_mappings(config, abi_map):
       """Generate aggregated mapping files."""
       # Implementation here
       pass
   ```

2. **Create templates** in `templates/mappings/` (e.g., `mapping_aggregated.ts.j2`)

3. **Update the orchestrator** in `generate/orchestrator.py`:
   - Add a new `mappings_mode` option (e.g., `"aggregated"`)
   - Call the new generator when selected

4. **Update the config model** in `config/model.py` if needed

5. **Update validation** in `config/validation.py` to accept the new mode

6. **Add tests** for the new mapping style

### Adding a New Complexity Level

If you need a new complexity level beyond basic/intermediate/advanced:

1. **Update `config/model.py`**:
   - Add new fields to `SubgraphConfig` or `ContractConfig`
   - Bump `config_version` if schema changes

2. **Update `config/validation.py`**:
   - Add validation for new complexity-specific fields

3. **Update generators**:
   - `generate/subgraph_yaml.py` – handle new YAML sections
   - `generate/schema.py` – handle new schema patterns
   - `generate/mappings_*.py` – handle new mapping patterns

4. **Update the wizard** in `interactive_wizard.py`:
   - Add the new complexity option
   - Collect required fields

5. **Update documentation**:
   - `docs/config-format.md` – document new fields
   - `docs/user-guide.md` – add examples

6. **Add comprehensive tests**

---

## CI/CD

### Current Status

CI/CD is **optional** per the development checklist (Milestone 11). If you want to set up CI:

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest --cov=subgraph_wizard --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Running CI Locally

You can simulate CI locally using Docker or by running the same commands:

```bash
# Install dependencies
pip install -e .
pip install pytest pytest-cov

# Run tests
pytest --cov=subgraph_wizard
```

---

## Debugging Tips

### Enable Debug Logging

Set the `LOG_LEVEL` environment variable:

```bash
export LOG_LEVEL=DEBUG
subgraph-wizard --config my-config.json --generate
```

Or in Python:
```python
import os
os.environ["LOG_LEVEL"] = "DEBUG"
```

### Dry Run Mode

Use `--dry-run` to preview what will be generated without writing files:

```bash
subgraph-wizard --config my-config.json --generate --dry-run
```

### Testing ABI Fetching

If testing Etherscan integration, make sure your `.env` file has valid API keys:

```bash
# Test with a known verified contract
subgraph-wizard
# Select "Fetch from explorer"
# Enter: 0x6B175474E89094C44Da98b954EedeAC495271d0F (DAI token)
```

### Common Issues

1. **Import errors**: Make sure you've installed the package: `pip install -e .`
2. **Template not found**: Check that templates are in `templates/` relative to the package root
3. **ABI fetch fails**: Verify API keys in `.env` and that the contract is verified on the explorer
4. **Validation errors**: Check `config/validation.py` for specific validation rules

### Using a Debugger

```bash
# Run with Python debugger
python -m pdb -m subgraph_wizard --config my-config.json
```

Or use your IDE's debugger (VS Code, PyCharm, etc.) to set breakpoints.

---

## Additional Resources

- [Architecture Documentation](architecture.md) – System design overview
- [User Guide](user-guide.md) – How to use the wizard
- [Config Format](config-format.md) – Configuration file reference
- [Development Checklist](../development_checklist.md) – Step-by-step development roadmap

---

## Getting Help

- Open an issue on GitHub for bugs or feature requests
- Check existing issues and PRs for similar questions
- Review the architecture documentation for system design questions

---

Happy contributing! 🚀
