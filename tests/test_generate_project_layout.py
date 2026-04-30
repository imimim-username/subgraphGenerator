"""Tests for project layout generation."""

import pytest
from pathlib import Path

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.project_layout import prepare_project_structure


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample SubgraphConfig for testing."""
    return SubgraphConfig(
        name="test-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "test-output"),
        mappings_mode="auto",
        contracts=[
            ContractConfig(
                name="TestContract",
                address="0x1234567890123456789012345678901234567890",
                start_block=12345678,
                abi_path="TestContract.json",
            )
        ],
    )


class TestPrepareProjectStructure:
    """Tests for prepare_project_structure function."""
    
    def test_creates_root_directory(self, sample_config):
        """Test that root directory is created."""
        paths = prepare_project_structure(sample_config)
        
        assert paths["root_dir"].exists()
        assert paths["root_dir"].is_dir()
        assert str(paths["root_dir"]) == sample_config.output_dir
    
    def test_creates_abis_directory(self, sample_config):
        """Test that abis directory is created."""
        paths = prepare_project_structure(sample_config)
        
        assert paths["abis_dir"].exists()
        assert paths["abis_dir"].is_dir()
        assert paths["abis_dir"] == paths["root_dir"] / "abis"
    
    def test_creates_src_directory(self, sample_config):
        """Test that src directory is created."""
        paths = prepare_project_structure(sample_config)
        
        assert paths["src_dir"].exists()
        assert paths["src_dir"].is_dir()
        assert paths["src_dir"] == paths["root_dir"] / "src"
    
    def test_creates_mappings_directory(self, sample_config):
        """Test that mappings directory is created."""
        paths = prepare_project_structure(sample_config)
        
        assert paths["mappings_dir"].exists()
        assert paths["mappings_dir"].is_dir()
        assert paths["mappings_dir"] == paths["root_dir"] / "src" / "mappings"
    
    def test_returns_correct_path_types(self, sample_config):
        """Test that all returned paths are Path objects."""
        paths = prepare_project_structure(sample_config)
        
        assert isinstance(paths["root_dir"], Path)
        assert isinstance(paths["abis_dir"], Path)
        assert isinstance(paths["src_dir"], Path)
        assert isinstance(paths["mappings_dir"], Path)
    
    def test_idempotent_creation(self, sample_config):
        """Test that calling twice doesn't raise errors."""
        paths1 = prepare_project_structure(sample_config)
        paths2 = prepare_project_structure(sample_config)
        
        # Both calls should succeed and return same paths
        assert paths1["root_dir"] == paths2["root_dir"]
        assert paths1["abis_dir"] == paths2["abis_dir"]
        assert paths1["src_dir"] == paths2["src_dir"]
        assert paths1["mappings_dir"] == paths2["mappings_dir"]
    
    def test_creates_nested_output_dir(self, tmp_path):
        """Test creation of deeply nested output directory."""
        config = SubgraphConfig(
            name="nested-subgraph",
            network="optimism",
            output_dir=str(tmp_path / "a" / "b" / "c" / "output"),
            mappings_mode="auto",
            contracts=[],
        )
        
        paths = prepare_project_structure(config)
        
        assert paths["root_dir"].exists()
        assert paths["mappings_dir"].exists()

