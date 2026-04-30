"""Tests for package.json generation."""

import json
import pytest

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.package_json import (
    render_package_json,
    _sanitize_package_name,
    DEFAULT_GRAPH_CLI_VERSION,
    DEFAULT_GRAPH_TS_VERSION,
)


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample SubgraphConfig for testing."""
    return SubgraphConfig(
        name="test-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "generated"),
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


class TestRenderPackageJson:
    """Tests for package.json rendering."""
    
    def test_generates_valid_json(self, sample_config):
        """Test that output is valid JSON."""
        package_json = render_package_json(sample_config)
        
        # Should not raise an exception
        parsed = json.loads(package_json)
        
        assert isinstance(parsed, dict)
    
    def test_has_correct_name(self, sample_config):
        """Test that package name is set correctly."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        assert parsed["name"] == "test-subgraph"
    
    def test_has_description_with_network(self, sample_config):
        """Test that description includes network."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        assert "ethereum" in parsed["description"]
    
    def test_has_required_scripts(self, sample_config):
        """Test that required scripts are present."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        scripts = parsed["scripts"]
        
        assert "codegen" in scripts
        assert "build" in scripts
        assert "deploy" in scripts
    
    def test_codegen_script_uses_graph_codegen(self, sample_config):
        """Test that codegen script uses graph codegen command."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        assert parsed["scripts"]["codegen"] == "graph codegen"
    
    def test_build_script_uses_graph_build(self, sample_config):
        """Test that build script uses graph build command."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        assert parsed["scripts"]["build"] == "graph build"
    
    def test_has_local_deployment_scripts(self, sample_config):
        """Test that local deployment scripts are present."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        scripts = parsed["scripts"]
        
        assert "create-local" in scripts
        assert "remove-local" in scripts
        assert "deploy-local" in scripts
    
    def test_has_graph_cli_dependency(self, sample_config):
        """Test that @graphprotocol/graph-cli is a dependency."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        deps = parsed["dependencies"]
        
        assert "@graphprotocol/graph-cli" in deps
    
    def test_has_graph_ts_dependency(self, sample_config):
        """Test that @graphprotocol/graph-ts is a dependency."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        deps = parsed["dependencies"]
        
        assert "@graphprotocol/graph-ts" in deps
    
    def test_uses_default_versions(self, sample_config):
        """Test that default versions are used when not specified."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        deps = parsed["dependencies"]
        
        assert deps["@graphprotocol/graph-cli"] == DEFAULT_GRAPH_CLI_VERSION
        assert deps["@graphprotocol/graph-ts"] == DEFAULT_GRAPH_TS_VERSION
    
    def test_accepts_custom_versions(self, sample_config):
        """Test that custom versions can be specified."""
        package_json = render_package_json(
            sample_config,
            graph_cli_version="0.50.0",
            graph_ts_version="0.30.0",
        )
        parsed = json.loads(package_json)
        
        deps = parsed["dependencies"]
        
        assert deps["@graphprotocol/graph-cli"] == "0.50.0"
        assert deps["@graphprotocol/graph-ts"] == "0.30.0"
    
    def test_has_version_field(self, sample_config):
        """Test that version field is present."""
        package_json = render_package_json(sample_config)
        parsed = json.loads(package_json)
        
        assert "version" in parsed
        assert parsed["version"] == "0.0.1"


class TestSanitizePackageName:
    """Tests for package name sanitization."""
    
    def test_converts_to_lowercase(self):
        """Test that name is converted to lowercase."""
        assert _sanitize_package_name("MySubgraph") == "mysubgraph"
    
    def test_replaces_spaces_with_hyphens(self):
        """Test that spaces are replaced with hyphens."""
        assert _sanitize_package_name("my subgraph") == "my-subgraph"
    
    def test_replaces_underscores_with_hyphens(self):
        """Test that underscores are replaced with hyphens."""
        assert _sanitize_package_name("my_subgraph") == "my-subgraph"
    
    def test_removes_invalid_characters(self):
        """Test that invalid characters are removed."""
        assert _sanitize_package_name("my@subgraph!") == "mysubgraph"
    
    def test_removes_leading_dots(self):
        """Test that leading dots are removed."""
        assert _sanitize_package_name(".hidden") == "hidden"
    
    def test_removes_leading_hyphens(self):
        """Test that leading hyphens are removed."""
        assert _sanitize_package_name("-mysubgraph") == "mysubgraph"
    
    def test_handles_empty_result(self):
        """Test that empty result becomes 'subgraph'."""
        assert _sanitize_package_name("!!!") == "subgraph"
    
    def test_handles_normal_name(self):
        """Test that normal names are unchanged."""
        assert _sanitize_package_name("uniswap-v3") == "uniswap-v3"


class TestPackageJsonWithDifferentConfigs:
    """Tests for package.json with various configurations."""
    
    def test_name_with_spaces_is_sanitized(self, tmp_path):
        """Test that subgraph names with spaces are sanitized."""
        config = SubgraphConfig(
            name="My Awesome Subgraph",
            network="optimism",
            output_dir=str(tmp_path / "generated"),
            mappings_mode="auto",
            contracts=[
                ContractConfig(
                    name="Token",
                    address="0x1234567890123456789012345678901234567890",
                    start_block=1000,
                    abi_path="Token.json",
                )
            ],
        )
        
        package_json = render_package_json(config)
        parsed = json.loads(package_json)
        
        assert parsed["name"] == "my-awesome-subgraph"
    
    def test_description_reflects_network(self, tmp_path):
        """Test that description uses the correct network."""
        config = SubgraphConfig(
            name="my-subgraph",
            network="arbitrum",
            output_dir=str(tmp_path / "generated"),
            mappings_mode="stub",
            contracts=[
                ContractConfig(
                    name="Token",
                    address="0x1234567890123456789012345678901234567890",
                    start_block=1000,
                    abi_path="Token.json",
                )
            ],
        )
        
        package_json = render_package_json(config)
        parsed = json.loads(package_json)
        
        assert "arbitrum" in parsed["description"]
