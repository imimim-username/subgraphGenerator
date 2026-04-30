"""Tests for the basic generation flow (end-to-end MVP)."""

import pytest
from pathlib import Path

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.orchestrator import generate_subgraph_project


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample SubgraphConfig for testing."""
    return SubgraphConfig(
        name="test-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "generated-subgraph"),
        mappings_mode="auto",
        contracts=[
            ContractConfig(
                name="TestToken",
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                start_block=12345678,
                abi_path="TestToken.json",
            )
        ],
    )


@pytest.fixture
def multi_contract_config(tmp_path):
    """Create a config with multiple contracts."""
    return SubgraphConfig(
        name="multi-contract-subgraph",
        network="optimism",
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


class TestGenerateSubgraphProject:
    """Tests for the full generation pipeline."""
    
    def test_creates_subgraph_yaml(self, sample_config):
        """Test that subgraph.yaml is created."""
        generate_subgraph_project(sample_config)
        
        subgraph_yaml = Path(sample_config.output_dir) / "subgraph.yaml"
        assert subgraph_yaml.exists()
        assert subgraph_yaml.is_file()
    
    def test_creates_schema_graphql(self, sample_config):
        """Test that schema.graphql is created."""
        generate_subgraph_project(sample_config)
        
        schema = Path(sample_config.output_dir) / "schema.graphql"
        assert schema.exists()
        assert schema.is_file()
    
    def test_creates_mapping_file(self, sample_config):
        """Test that mapping file is created for the contract."""
        generate_subgraph_project(sample_config)
        
        mapping = Path(sample_config.output_dir) / "src" / "mappings" / "TestToken.ts"
        assert mapping.exists()
        assert mapping.is_file()
    
    def test_creates_directory_structure(self, sample_config):
        """Test that all required directories are created."""
        generate_subgraph_project(sample_config)
        
        root = Path(sample_config.output_dir)
        assert (root / "abis").is_dir()
        assert (root / "src").is_dir()
        assert (root / "src" / "mappings").is_dir()
    
    def test_subgraph_yaml_contains_network(self, sample_config):
        """Test that subgraph.yaml contains correct network."""
        generate_subgraph_project(sample_config)
        
        content = (Path(sample_config.output_dir) / "subgraph.yaml").read_text()
        assert "network: ethereum" in content
    
    def test_subgraph_yaml_contains_contract_name(self, sample_config):
        """Test that subgraph.yaml contains contract name."""
        generate_subgraph_project(sample_config)
        
        content = (Path(sample_config.output_dir) / "subgraph.yaml").read_text()
        assert "TestToken" in content
    
    def test_schema_contains_entity(self, sample_config):
        """Test that schema.graphql contains entity definition."""
        generate_subgraph_project(sample_config)
        
        content = (Path(sample_config.output_dir) / "schema.graphql").read_text()
        assert "type TestTokenEvent @entity(immutable: true)" in content
    
    def test_schema_contains_standard_fields(self, sample_config):
        """Test that schema entities have standard metadata fields."""
        generate_subgraph_project(sample_config)
        
        content = (Path(sample_config.output_dir) / "schema.graphql").read_text()
        assert "blockNumber: BigInt!" in content
        assert "blockTimestamp: BigInt!" in content
        assert "transactionHash: Bytes!" in content
    
    def test_mapping_contains_handler_function(self, sample_config):
        """Test that mapping file contains handler function."""
        generate_subgraph_project(sample_config)
        
        mapping = Path(sample_config.output_dir) / "src" / "mappings" / "TestToken.ts"
        content = mapping.read_text()
        assert "export function" in content
        assert "handleTestTokenEvent" in content
    
    def test_mapping_contains_entity_save(self, sample_config):
        """Test that mapping file saves entities."""
        generate_subgraph_project(sample_config)
        
        mapping = Path(sample_config.output_dir) / "src" / "mappings" / "TestToken.ts"
        content = mapping.read_text()
        assert "entity.save()" in content
    
    def test_multi_contract_creates_all_mappings(self, multi_contract_config):
        """Test that multiple contract configs create multiple mapping files."""
        generate_subgraph_project(multi_contract_config)
        
        mappings_dir = Path(multi_contract_config.output_dir) / "src" / "mappings"
        assert (mappings_dir / "TokenA.ts").exists()
        assert (mappings_dir / "TokenB.ts").exists()
    
    def test_multi_contract_schema_has_all_entities(self, multi_contract_config):
        """Test that schema has entities for all contracts."""
        generate_subgraph_project(multi_contract_config)
        
        content = (Path(multi_contract_config.output_dir) / "schema.graphql").read_text()
        assert "type TokenAEvent @entity(immutable: true)" in content
        assert "type TokenBEvent @entity(immutable: true)" in content
    
    def test_dry_run_does_not_create_files(self, sample_config):
        """Test that dry run mode does not create any files."""
        generate_subgraph_project(sample_config, dry_run=True)
        
        root = Path(sample_config.output_dir)
        assert not root.exists()
    
    def test_dry_run_does_not_fail(self, sample_config):
        """Test that dry run mode completes without error."""
        # Should not raise any exceptions
        generate_subgraph_project(sample_config, dry_run=True)


class TestStubMappingsMode:
    """Tests for stub mappings mode."""
    
    def test_stub_mode_generates_stub_mappings(self, tmp_path):
        """Test that stub mode generates stub mapping files with TODO comments."""
        config = SubgraphConfig(
            name="stub-subgraph",
            network="ethereum",
            output_dir=str(tmp_path / "stub-output"),
            mappings_mode="stub",
            contracts=[
                ContractConfig(
                    name="TestContract",
                    address="0x1234567890123456789012345678901234567890",
                    start_block=1,
                    abi_path="Test.json",
                )
            ],
        )
        
        generate_subgraph_project(config)
        
        # Should create all expected files
        assert (Path(config.output_dir) / "subgraph.yaml").exists()
        assert (Path(config.output_dir) / "schema.graphql").exists()
        assert (Path(config.output_dir) / "package.json").exists()
        assert (Path(config.output_dir) / "README.md").exists()
        
        # Should create stub mapping file
        mapping_path = Path(config.output_dir) / "src" / "mappings" / "TestContract.ts"
        assert mapping_path.exists()
        
        # Stub mapping should contain TODO comments
        mapping_content = mapping_path.read_text()
        assert "TODO:" in mapping_content

