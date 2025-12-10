"""End-to-end tests for basic mode generation pipeline.

This module tests the full generation pipeline for basic complexity mode,
loading fixture configs and verifying that generated subgraphs have the
correct structure and content.
"""

import json
import shutil
import pytest
import yaml
from pathlib import Path

from subgraph_wizard.config.io import load_config
from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.orchestrator import generate_subgraph_project


# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def basic_config_path(fixtures_dir):
    """Return the path to the basic config fixture."""
    return fixtures_dir / "basic_config.json"


@pytest.fixture
def sample_abi_path(fixtures_dir):
    """Return the path to the sample ABI fixture."""
    return fixtures_dir / "SampleToken.json"


@pytest.fixture
def basic_config(basic_config_path, tmp_path):
    """Load basic config and update output_dir to use temp directory."""
    config = load_config(basic_config_path)
    # Override output_dir to use a temp directory for test isolation
    config.output_dir = str(tmp_path / "generated-subgraph")
    return config


@pytest.fixture
def basic_config_with_abi(basic_config, sample_abi_path):
    """Load basic config and set up ABI in the output directory.
    
    This fixture ensures the ABI file is available in the abis/ directory
    before generation, simulating what the wizard does.
    """
    output_dir = Path(basic_config.output_dir)
    abis_dir = output_dir / "abis"
    abis_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy the sample ABI to the output directory
    shutil.copy(sample_abi_path, abis_dir / "SampleToken.json")
    
    return basic_config


class TestBasicModeFileExistence:
    """Test that all expected files are created in basic mode."""
    
    def test_creates_subgraph_yaml(self, basic_config_with_abi):
        """Test that subgraph.yaml is created."""
        generate_subgraph_project(basic_config_with_abi)
        
        subgraph_yaml = Path(basic_config_with_abi.output_dir) / "subgraph.yaml"
        assert subgraph_yaml.exists(), "subgraph.yaml should exist"
        assert subgraph_yaml.is_file(), "subgraph.yaml should be a file"
    
    def test_creates_schema_graphql(self, basic_config_with_abi):
        """Test that schema.graphql is created."""
        generate_subgraph_project(basic_config_with_abi)
        
        schema = Path(basic_config_with_abi.output_dir) / "schema.graphql"
        assert schema.exists(), "schema.graphql should exist"
        assert schema.is_file(), "schema.graphql should be a file"
    
    def test_creates_mapping_files(self, basic_config_with_abi):
        """Test that mapping files are created for all contracts."""
        generate_subgraph_project(basic_config_with_abi)
        
        for contract in basic_config_with_abi.contracts:
            mapping = Path(basic_config_with_abi.output_dir) / "src" / "mappings" / f"{contract.name}.ts"
            assert mapping.exists(), f"Mapping file for {contract.name} should exist"
            assert mapping.is_file(), f"Mapping for {contract.name} should be a file"
    
    def test_creates_package_json(self, basic_config_with_abi):
        """Test that package.json is created."""
        generate_subgraph_project(basic_config_with_abi)
        
        package_json = Path(basic_config_with_abi.output_dir) / "package.json"
        assert package_json.exists(), "package.json should exist"
        assert package_json.is_file(), "package.json should be a file"
    
    def test_creates_readme(self, basic_config_with_abi):
        """Test that README.md is created."""
        generate_subgraph_project(basic_config_with_abi)
        
        readme = Path(basic_config_with_abi.output_dir) / "README.md"
        assert readme.exists(), "README.md should exist"
        assert readme.is_file(), "README.md should be a file"
    
    def test_creates_directory_structure(self, basic_config_with_abi):
        """Test that all required directories are created."""
        generate_subgraph_project(basic_config_with_abi)
        
        root = Path(basic_config_with_abi.output_dir)
        assert (root / "abis").is_dir(), "abis/ directory should exist"
        assert (root / "src").is_dir(), "src/ directory should exist"
        assert (root / "src" / "mappings").is_dir(), "src/mappings/ directory should exist"


class TestSubgraphYamlContent:
    """Test the content of generated subgraph.yaml."""
    
    def test_contains_correct_network(self, basic_config_with_abi):
        """Test that subgraph.yaml contains the correct network."""
        generate_subgraph_project(basic_config_with_abi)
        
        subgraph_yaml_path = Path(basic_config_with_abi.output_dir) / "subgraph.yaml"
        content = yaml.safe_load(subgraph_yaml_path.read_text())
        
        # Check dataSources network
        assert "dataSources" in content, "subgraph.yaml should have dataSources"
        assert len(content["dataSources"]) > 0, "Should have at least one dataSource"
        
        for ds in content["dataSources"]:
            assert ds.get("network") == basic_config_with_abi.network, \
                f"Expected network {basic_config_with_abi.network}"
    
    def test_contains_correct_datasources(self, basic_config_with_abi):
        """Test that subgraph.yaml contains correct dataSources for all contracts."""
        generate_subgraph_project(basic_config_with_abi)
        
        subgraph_yaml_path = Path(basic_config_with_abi.output_dir) / "subgraph.yaml"
        content = yaml.safe_load(subgraph_yaml_path.read_text())
        
        datasources = content.get("dataSources", [])
        datasource_names = [ds.get("name") for ds in datasources]
        
        for contract in basic_config_with_abi.contracts:
            assert contract.name in datasource_names, \
                f"Contract {contract.name} should have a dataSource"
    
    def test_datasource_has_correct_address(self, basic_config_with_abi):
        """Test that dataSource has the correct contract address."""
        generate_subgraph_project(basic_config_with_abi)
        
        subgraph_yaml_path = Path(basic_config_with_abi.output_dir) / "subgraph.yaml"
        content = yaml.safe_load(subgraph_yaml_path.read_text())
        
        for ds in content.get("dataSources", []):
            source = ds.get("source", {})
            address = source.get("address")
            
            # Find matching contract
            matching_contracts = [
                c for c in basic_config_with_abi.contracts 
                if c.name == ds.get("name")
            ]
            if matching_contracts:
                expected_address = matching_contracts[0].address
                assert address == expected_address, \
                    f"Expected address {expected_address}, got {address}"
    
    def test_datasource_has_correct_start_block(self, basic_config_with_abi):
        """Test that dataSource has the correct start block."""
        generate_subgraph_project(basic_config_with_abi)
        
        subgraph_yaml_path = Path(basic_config_with_abi.output_dir) / "subgraph.yaml"
        content = yaml.safe_load(subgraph_yaml_path.read_text())
        
        for ds in content.get("dataSources", []):
            source = ds.get("source", {})
            start_block = source.get("startBlock")
            
            # Find matching contract
            matching_contracts = [
                c for c in basic_config_with_abi.contracts 
                if c.name == ds.get("name")
            ]
            if matching_contracts:
                expected_start_block = matching_contracts[0].start_block
                assert start_block == expected_start_block, \
                    f"Expected start block {expected_start_block}, got {start_block}"
    
    def test_datasource_has_event_handlers(self, basic_config_with_abi):
        """Test that dataSources have event handlers defined."""
        generate_subgraph_project(basic_config_with_abi)
        
        subgraph_yaml_path = Path(basic_config_with_abi.output_dir) / "subgraph.yaml"
        content = yaml.safe_load(subgraph_yaml_path.read_text())
        
        for ds in content.get("dataSources", []):
            mapping = ds.get("mapping", {})
            event_handlers = mapping.get("eventHandlers", [])
            
            # With a real ABI, we should have event handlers
            assert len(event_handlers) > 0, \
                f"DataSource {ds.get('name')} should have event handlers"


class TestSchemaGraphqlContent:
    """Test the content of generated schema.graphql."""
    
    def test_contains_entity_for_each_event(self, basic_config_with_abi):
        """Test that schema contains entity types for ABI events."""
        generate_subgraph_project(basic_config_with_abi)
        
        schema_path = Path(basic_config_with_abi.output_dir) / "schema.graphql"
        content = schema_path.read_text()
        
        # The sample ABI has Transfer and Approval events
        assert "type Transfer @entity" in content, \
            "Schema should have Transfer entity"
        assert "type Approval @entity" in content, \
            "Schema should have Approval entity"
    
    def test_entity_has_id_field(self, basic_config_with_abi):
        """Test that entities have an id field."""
        generate_subgraph_project(basic_config_with_abi)
        
        schema_path = Path(basic_config_with_abi.output_dir) / "schema.graphql"
        content = schema_path.read_text()
        
        # Should have ID field
        assert "id: ID!" in content or "id: Bytes!" in content, \
            "Entity should have an id field"
    
    def test_entity_has_metadata_fields(self, basic_config_with_abi):
        """Test that entities have standard metadata fields."""
        generate_subgraph_project(basic_config_with_abi)
        
        schema_path = Path(basic_config_with_abi.output_dir) / "schema.graphql"
        content = schema_path.read_text()
        
        # Standard metadata fields
        assert "blockNumber:" in content, "Should have blockNumber field"
        assert "blockTimestamp:" in content, "Should have blockTimestamp field"
        assert "transactionHash:" in content, "Should have transactionHash field"
    
    def test_entity_has_event_parameters(self, basic_config_with_abi):
        """Test that entities have fields for event parameters."""
        generate_subgraph_project(basic_config_with_abi)
        
        schema_path = Path(basic_config_with_abi.output_dir) / "schema.graphql"
        content = schema_path.read_text()
        
        # Transfer event has from, to, value
        assert "from:" in content, "Transfer should have 'from' field"
        assert "to:" in content, "Transfer should have 'to' field"
        assert "value:" in content, "Transfer should have 'value' field"


class TestMappingContent:
    """Test the content of generated mapping files."""
    
    def test_mapping_has_imports(self, basic_config_with_abi):
        """Test that mapping files have necessary imports."""
        generate_subgraph_project(basic_config_with_abi)
        
        for contract in basic_config_with_abi.contracts:
            mapping_path = Path(basic_config_with_abi.output_dir) / "src" / "mappings" / f"{contract.name}.ts"
            content = mapping_path.read_text()
            
            assert "import" in content, "Mapping should have imports"
    
    def test_mapping_has_handler_functions(self, basic_config_with_abi):
        """Test that mapping files have handler functions for events."""
        generate_subgraph_project(basic_config_with_abi)
        
        for contract in basic_config_with_abi.contracts:
            mapping_path = Path(basic_config_with_abi.output_dir) / "src" / "mappings" / f"{contract.name}.ts"
            content = mapping_path.read_text()
            
            # Should have export function declarations
            assert "export function" in content, \
                "Mapping should have exported functions"
            
            # Should have handler for Transfer event
            assert "handleTransfer" in content, \
                "Should have handleTransfer handler"
            
            # Should have handler for Approval event
            assert "handleApproval" in content, \
                "Should have handleApproval handler"
    
    def test_mapping_saves_entities(self, basic_config_with_abi):
        """Test that auto-mode mapping files save entities."""
        generate_subgraph_project(basic_config_with_abi)
        
        for contract in basic_config_with_abi.contracts:
            mapping_path = Path(basic_config_with_abi.output_dir) / "src" / "mappings" / f"{contract.name}.ts"
            content = mapping_path.read_text()
            
            # Auto mode should save entities
            assert "entity.save()" in content or ".save()" in content, \
                "Auto-mode mapping should save entities"


class TestPackageJsonContent:
    """Test the content of generated package.json."""
    
    def test_has_valid_json(self, basic_config_with_abi):
        """Test that package.json is valid JSON."""
        generate_subgraph_project(basic_config_with_abi)
        
        package_json_path = Path(basic_config_with_abi.output_dir) / "package.json"
        content = package_json_path.read_text()
        
        # Should be valid JSON
        data = json.loads(content)
        assert isinstance(data, dict), "package.json should be a JSON object"
    
    def test_has_required_dependencies(self, basic_config_with_abi):
        """Test that package.json has required Graph dependencies."""
        generate_subgraph_project(basic_config_with_abi)
        
        package_json_path = Path(basic_config_with_abi.output_dir) / "package.json"
        data = json.loads(package_json_path.read_text())
        
        # Should have devDependencies or dependencies
        deps = data.get("devDependencies", {}) or data.get("dependencies", {})
        
        assert "@graphprotocol/graph-cli" in deps, \
            "Should have @graphprotocol/graph-cli dependency"
        assert "@graphprotocol/graph-ts" in deps, \
            "Should have @graphprotocol/graph-ts dependency"
    
    def test_has_build_scripts(self, basic_config_with_abi):
        """Test that package.json has build scripts."""
        generate_subgraph_project(basic_config_with_abi)
        
        package_json_path = Path(basic_config_with_abi.output_dir) / "package.json"
        data = json.loads(package_json_path.read_text())
        
        scripts = data.get("scripts", {})
        
        assert "codegen" in scripts, "Should have codegen script"
        assert "build" in scripts, "Should have build script"


class TestReadmeContent:
    """Test the content of generated README.md."""
    
    def test_contains_network_info(self, basic_config_with_abi):
        """Test that README contains network information."""
        generate_subgraph_project(basic_config_with_abi)
        
        readme_path = Path(basic_config_with_abi.output_dir) / "README.md"
        content = readme_path.read_text()
        
        assert basic_config_with_abi.network in content, \
            f"README should mention network: {basic_config_with_abi.network}"
    
    def test_contains_contract_info(self, basic_config_with_abi):
        """Test that README contains contract information."""
        generate_subgraph_project(basic_config_with_abi)
        
        readme_path = Path(basic_config_with_abi.output_dir) / "README.md"
        content = readme_path.read_text()
        
        for contract in basic_config_with_abi.contracts:
            assert contract.name in content, \
                f"README should mention contract: {contract.name}"
    
    def test_contains_build_instructions(self, basic_config_with_abi):
        """Test that README contains build instructions."""
        generate_subgraph_project(basic_config_with_abi)
        
        readme_path = Path(basic_config_with_abi.output_dir) / "README.md"
        content = readme_path.read_text()
        
        assert "codegen" in content.lower() or "graph codegen" in content.lower(), \
            "README should mention codegen"
        assert "build" in content.lower() or "graph build" in content.lower(), \
            "README should mention build"


class TestStubModeGeneration:
    """Test generation in stub mode."""
    
    @pytest.fixture
    def stub_config_with_abi(self, basic_config_with_abi):
        """Create a config with stub mappings mode."""
        basic_config_with_abi.mappings_mode = "stub"
        return basic_config_with_abi
    
    def test_stub_mode_generates_all_files(self, stub_config_with_abi):
        """Test that stub mode generates all expected files."""
        generate_subgraph_project(stub_config_with_abi)
        
        root = Path(stub_config_with_abi.output_dir)
        
        assert (root / "subgraph.yaml").exists(), "subgraph.yaml should exist"
        assert (root / "schema.graphql").exists(), "schema.graphql should exist"
        assert (root / "package.json").exists(), "package.json should exist"
        assert (root / "README.md").exists(), "README.md should exist"
        
        for contract in stub_config_with_abi.contracts:
            mapping = root / "src" / "mappings" / f"{contract.name}.ts"
            assert mapping.exists(), f"Mapping for {contract.name} should exist"
    
    def test_stub_mode_has_todo_comments(self, stub_config_with_abi):
        """Test that stub mode mappings have TODO comments."""
        generate_subgraph_project(stub_config_with_abi)
        
        for contract in stub_config_with_abi.contracts:
            mapping_path = Path(stub_config_with_abi.output_dir) / "src" / "mappings" / f"{contract.name}.ts"
            content = mapping_path.read_text()
            
            assert "TODO" in content, "Stub mapping should have TODO comments"


class TestMultiContractGeneration:
    """Test generation with multiple contracts."""
    
    @pytest.fixture
    def multi_contract_config(self, tmp_path, sample_abi_path):
        """Create a config with multiple contracts."""
        config = SubgraphConfig(
            name="multi-contract-subgraph",
            network="ethereum",
            output_dir=str(tmp_path / "multi-subgraph"),
            mappings_mode="auto",
            contracts=[
                ContractConfig(
                    name="TokenA",
                    address="0x1111111111111111111111111111111111111111",
                    start_block=1000000,
                    abi_path="TokenA.json",
                ),
                ContractConfig(
                    name="TokenB",
                    address="0x2222222222222222222222222222222222222222",
                    start_block=2000000,
                    abi_path="TokenB.json",
                ),
            ],
        )
        
        # Set up ABIs directory with both ABIs
        abis_dir = Path(config.output_dir) / "abis"
        abis_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(sample_abi_path, abis_dir / "TokenA.json")
        shutil.copy(sample_abi_path, abis_dir / "TokenB.json")
        
        return config
    
    def test_creates_mapping_for_each_contract(self, multi_contract_config):
        """Test that each contract gets its own mapping file."""
        generate_subgraph_project(multi_contract_config)
        
        mappings_dir = Path(multi_contract_config.output_dir) / "src" / "mappings"
        
        assert (mappings_dir / "TokenA.ts").exists(), "TokenA mapping should exist"
        assert (mappings_dir / "TokenB.ts").exists(), "TokenB mapping should exist"
    
    def test_subgraph_yaml_has_all_datasources(self, multi_contract_config):
        """Test that subgraph.yaml has dataSources for all contracts."""
        generate_subgraph_project(multi_contract_config)
        
        subgraph_yaml_path = Path(multi_contract_config.output_dir) / "subgraph.yaml"
        content = yaml.safe_load(subgraph_yaml_path.read_text())
        
        datasources = content.get("dataSources", [])
        datasource_names = [ds.get("name") for ds in datasources]
        
        assert "TokenA" in datasource_names, "TokenA should be in dataSources"
        assert "TokenB" in datasource_names, "TokenB should be in dataSources"
        assert len(datasources) == 2, "Should have exactly 2 dataSources"


class TestLoadFromFixture:
    """Test loading config directly from fixture file."""
    
    def test_load_fixture_config(self, basic_config_path):
        """Test that fixture config can be loaded successfully."""
        config = load_config(basic_config_path)
        
        assert config.name == "sample-token-subgraph"
        assert config.network == "ethereum"
        assert config.mappings_mode == "auto"
        assert config.complexity == "basic"
        assert len(config.contracts) == 1
    
    def test_fixture_contract_details(self, basic_config_path):
        """Test that fixture config has correct contract details."""
        config = load_config(basic_config_path)
        
        contract = config.contracts[0]
        assert contract.name == "SampleToken"
        assert contract.address == "0x6B175474E89094C44Da98b954EedeAC495271d0F"
        assert contract.start_block == 10000000
        assert contract.abi_path == "SampleToken.json"
