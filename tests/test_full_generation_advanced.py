"""End-to-end tests for advanced complexity subgraph generation.

Tests the full generation pipeline with templates and dynamic data sources,
verifying that all expected files are generated with correct content.
"""

import json
import shutil
import pytest
import yaml
from pathlib import Path

from subgraph_wizard.config.model import SubgraphConfig
from subgraph_wizard.config.io import load_config
from subgraph_wizard.generate.orchestrator import generate_subgraph_project


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def advanced_config(fixtures_dir, tmp_path):
    """Load the advanced config and copy ABIs to output directory."""
    config = load_config(fixtures_dir / "advanced_config.json")
    
    # Override output_dir to use temp directory
    config.output_dir = str(tmp_path / "output")
    
    # Copy ABI files to the abis directory
    output_path = Path(config.output_dir)
    abis_dir = output_path / "abis"
    abis_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy Factory.json
    shutil.copy(fixtures_dir / "Factory.json", abis_dir / "Factory.json")
    # Copy Pair.json
    shutil.copy(fixtures_dir / "Pair.json", abis_dir / "Pair.json")
    
    return config


class TestAdvancedFullGeneration:
    """End-to-end tests for advanced complexity generation."""
    
    def test_generates_all_expected_files(self, advanced_config, tmp_path):
        """Test that all expected files are generated."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        
        # Check that key files exist
        assert (output_path / "subgraph.yaml").exists()
        assert (output_path / "schema.graphql").exists()
        assert (output_path / "package.json").exists()
        assert (output_path / "README.md").exists()
        
        # Check that contract mapping exists
        assert (output_path / "src" / "mappings" / "Factory.ts").exists()
        
        # Check that template mapping exists
        assert (output_path / "src" / "mappings" / "Pair.ts").exists()
    
    def test_subgraph_yaml_has_templates_section(self, advanced_config, tmp_path):
        """Test that subgraph.yaml has templates section."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        subgraph_yaml_path = output_path / "subgraph.yaml"
        
        with open(subgraph_yaml_path) as f:
            manifest = yaml.safe_load(f)
        
        assert "templates" in manifest
        assert len(manifest["templates"]) == 1
        
        template = manifest["templates"][0]
        assert template["name"] == "Pair"
        assert template["kind"] == "ethereum"
    
    def test_subgraph_yaml_has_correct_data_sources(self, advanced_config, tmp_path):
        """Test that subgraph.yaml has correct data sources."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        subgraph_yaml_path = output_path / "subgraph.yaml"
        
        with open(subgraph_yaml_path) as f:
            manifest = yaml.safe_load(f)
        
        assert "dataSources" in manifest
        assert len(manifest["dataSources"]) == 1
        
        factory = manifest["dataSources"][0]
        assert factory["name"] == "Factory"
        assert factory["network"] == "ethereum"
    
    def test_factory_mapping_has_template_code(self, advanced_config, tmp_path):
        """Test that factory mapping has template instantiation code."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        mapping_path = output_path / "src" / "mappings" / "Factory.ts"
        
        with open(mapping_path) as f:
            content = f.read()
        
        # Should import Pair template
        assert "import { Pair } from" in content
        
        # Should have template creation code
        assert "Pair.create(" in content
    
    def test_pair_mapping_has_event_handlers(self, advanced_config, tmp_path):
        """Test that Pair mapping has expected event handlers."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        mapping_path = output_path / "src" / "mappings" / "Pair.ts"
        
        with open(mapping_path) as f:
            content = f.read()
        
        # Should have handlers for specified events
        assert "handleSwap" in content
        assert "handleSync" in content
        assert "handleMint" in content
        assert "handleBurn" in content
    
    def test_schema_has_template_entities(self, advanced_config, tmp_path):
        """Test that schema has entities from template events."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        schema_path = output_path / "schema.graphql"
        
        with open(schema_path) as f:
            content = f.read()
        
        # Should have entities for template events
        assert "type Swap @entity" in content
        assert "type Sync @entity" in content
        assert "type Mint @entity" in content
        assert "type Burn @entity" in content
    
    def test_schema_has_relationship_fields(self, advanced_config, tmp_path):
        """Test that schema has relationship fields from config."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        schema_path = output_path / "schema.graphql"
        
        with open(schema_path) as f:
            content = f.read()
        
        # Should have relationship fields
        # Based on advanced_config.json, Swap should have factory field
        assert "factory:" in content or "factory :" in content
    
    def test_template_event_handlers_in_subgraph_yaml(self, advanced_config, tmp_path):
        """Test that template has correct event handlers in subgraph.yaml."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        subgraph_yaml_path = output_path / "subgraph.yaml"
        
        with open(subgraph_yaml_path) as f:
            manifest = yaml.safe_load(f)
        
        template = manifest["templates"][0]
        event_handlers = template["mapping"]["eventHandlers"]
        
        handler_names = [h["handler"] for h in event_handlers]
        
        assert "handleSwap" in handler_names
        assert "handleSync" in handler_names
        assert "handleMint" in handler_names
        assert "handleBurn" in handler_names
    
    def test_factory_includes_pair_abi_reference(self, advanced_config, tmp_path):
        """Test that factory data source includes Pair ABI for template creation."""
        generate_subgraph_project(advanced_config)
        
        output_path = Path(advanced_config.output_dir)
        subgraph_yaml_path = output_path / "subgraph.yaml"
        
        with open(subgraph_yaml_path) as f:
            manifest = yaml.safe_load(f)
        
        factory = manifest["dataSources"][0]
        abis = factory["mapping"]["abis"]
        abi_names = [a["name"] for a in abis]
        
        # Factory should reference both Factory and Pair ABIs
        assert "Factory" in abi_names
        assert "Pair" in abi_names


class TestAdvancedDryRun:
    """Tests for dry-run mode with advanced complexity."""
    
    def test_dry_run_does_not_create_files(self, advanced_config, tmp_path):
        """Test that dry-run mode doesn't create files."""
        # Run in dry-run mode
        generate_subgraph_project(advanced_config, dry_run=True)
        
        output_path = Path(advanced_config.output_dir)
        
        # subgraph.yaml should not exist (only ABIs were pre-copied)
        assert not (output_path / "subgraph.yaml").exists()
        assert not (output_path / "schema.graphql").exists()


class TestAdvancedStubMode:
    """Tests for stub mode with advanced complexity."""
    
    def test_stub_mode_generates_template_mappings(self, fixtures_dir, tmp_path):
        """Test that stub mode generates template mappings with TODOs."""
        config = load_config(fixtures_dir / "advanced_config.json")
        config.output_dir = str(tmp_path / "output")
        config.mappings_mode = "stub"
        
        # Copy ABI files
        output_path = Path(config.output_dir)
        abis_dir = output_path / "abis"
        abis_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(fixtures_dir / "Factory.json", abis_dir / "Factory.json")
        shutil.copy(fixtures_dir / "Pair.json", abis_dir / "Pair.json")
        
        generate_subgraph_project(config)
        
        # Check Pair template mapping has TODOs
        pair_mapping = output_path / "src" / "mappings" / "Pair.ts"
        with open(pair_mapping) as f:
            content = f.read()
        
        assert "TODO" in content
