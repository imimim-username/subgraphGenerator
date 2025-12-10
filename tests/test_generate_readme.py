"""Tests for README generation."""

import pytest

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.readme import render_readme


# Sample ABI with a Transfer event
TRANSFER_ABI = [
    {
        "type": "event",
        "name": "Transfer",
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
]

# Sample ABI with multiple events
MULTI_EVENT_ABI = [
    {
        "type": "event",
        "name": "Transfer",
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "event",
        "name": "Approval",
        "inputs": [
            {"name": "owner", "type": "address", "indexed": True},
            {"name": "spender", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
]


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


@pytest.fixture
def multi_contract_config(tmp_path):
    """Create a config with multiple contracts."""
    return SubgraphConfig(
        name="multi-contract-subgraph",
        network="optimism",
        output_dir=str(tmp_path / "generated"),
        mappings_mode="auto",
        contracts=[
            ContractConfig(
                name="TokenA",
                address="0x1111111111111111111111111111111111111111",
                start_block=1000,
                abi_path="TokenA.json",
            ),
            ContractConfig(
                name="TokenB",
                address="0x2222222222222222222222222222222222222222",
                start_block=2000,
                abi_path="TokenB.json",
            ),
        ],
    )


@pytest.fixture
def stub_config(tmp_path):
    """Create a stub mode config."""
    return SubgraphConfig(
        name="stub-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "generated"),
        mappings_mode="stub",
        contracts=[
            ContractConfig(
                name="TestToken",
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                start_block=12345678,
                abi_path="TestToken.json",
            )
        ],
    )


class TestRenderReadme:
    """Tests for README rendering."""
    
    def test_includes_subgraph_name(self, sample_config):
        """Test that README includes the subgraph name."""
        readme = render_readme(sample_config)
        
        assert "test-subgraph" in readme
    
    def test_includes_network(self, sample_config):
        """Test that README includes the network."""
        readme = render_readme(sample_config)
        
        assert "ethereum" in readme
    
    def test_includes_contract_name(self, sample_config):
        """Test that README includes contract names."""
        readme = render_readme(sample_config)
        
        assert "TestToken" in readme
    
    def test_includes_contract_address(self, sample_config):
        """Test that README includes contract addresses."""
        readme = render_readme(sample_config)
        
        assert "0x6B175474E89094C44Da98b954EedeAC495271d0F" in readme
    
    def test_includes_start_block(self, sample_config):
        """Test that README includes start block."""
        readme = render_readme(sample_config)
        
        assert "12345678" in readme
    
    def test_includes_installation_instructions(self, sample_config):
        """Test that README includes installation instructions."""
        readme = render_readme(sample_config)
        
        assert "npm install" in readme
    
    def test_includes_codegen_command(self, sample_config):
        """Test that README includes codegen command."""
        readme = render_readme(sample_config)
        
        assert "npm run codegen" in readme or "graph codegen" in readme
    
    def test_includes_build_command(self, sample_config):
        """Test that README includes build command."""
        readme = render_readme(sample_config)
        
        assert "npm run build" in readme or "graph build" in readme
    
    def test_includes_project_structure(self, sample_config):
        """Test that README includes project structure documentation."""
        readme = render_readme(sample_config)
        
        assert "abis/" in readme
        assert "src/" in readme or "mappings/" in readme


class TestRenderReadmeWithMultipleContracts:
    """Tests for README with multiple contracts."""
    
    def test_includes_all_contract_names(self, multi_contract_config):
        """Test that README includes all contract names."""
        readme = render_readme(multi_contract_config)
        
        assert "TokenA" in readme
        assert "TokenB" in readme
    
    def test_includes_all_contract_addresses(self, multi_contract_config):
        """Test that README includes all contract addresses."""
        readme = render_readme(multi_contract_config)
        
        assert "0x1111111111111111111111111111111111111111" in readme
        assert "0x2222222222222222222222222222222222222222" in readme
    
    def test_includes_different_network(self, multi_contract_config):
        """Test that README includes the correct network."""
        readme = render_readme(multi_contract_config)
        
        assert "optimism" in readme


class TestRenderReadmeWithEvents:
    """Tests for README with event information."""
    
    def test_includes_event_names(self, sample_config):
        """Test that README includes event names when ABI is provided."""
        abi_map = {"TestToken": MULTI_EVENT_ABI}
        
        readme = render_readme(sample_config, abi_map)
        
        assert "Transfer" in readme
        assert "Approval" in readme


class TestRenderReadmeStubMode:
    """Tests for README with stub mapping mode."""
    
    def test_includes_stub_mode_info(self, stub_config):
        """Test that README includes stub mode information."""
        readme = render_readme(stub_config)
        
        assert "stub" in readme
    
    def test_includes_next_steps_for_stub(self, stub_config):
        """Test that README includes next steps for stub mode."""
        readme = render_readme(stub_config)
        
        # Should have information about implementing handlers
        assert "stub mappings" in readme.lower() or "todo" in readme.lower() or "next steps" in readme.lower()


class TestRenderReadmeWithDifferentConfigs:
    """Tests for README with various configurations."""
    
    def test_mappings_mode_shown(self, sample_config):
        """Test that mappings mode is shown in README."""
        readme = render_readme(sample_config)
        
        assert "auto" in readme.lower() or "Mapping Mode" in readme
    
    def test_complexity_shown(self, sample_config):
        """Test that complexity is shown in README."""
        readme = render_readme(sample_config)
        
        assert "basic" in readme.lower() or "Complexity" in readme
    
    def test_includes_deployment_instructions(self, sample_config):
        """Test that README includes deployment instructions."""
        readme = render_readme(sample_config)
        
        # Should mention deployment
        assert "deploy" in readme.lower()
    
    def test_includes_subgraph_studio_reference(self, sample_config):
        """Test that README includes Subgraph Studio reference."""
        readme = render_readme(sample_config)
        
        # Should mention Subgraph Studio
        assert "studio" in readme.lower() or "graph auth" in readme.lower()


class TestRenderReadmeMarkdown:
    """Tests for README markdown formatting."""
    
    def test_has_title_heading(self, sample_config):
        """Test that README has a title heading."""
        readme = render_readme(sample_config)
        
        # Should start with a heading
        assert readme.strip().startswith("#")
    
    def test_has_code_blocks(self, sample_config):
        """Test that README has code blocks."""
        readme = render_readme(sample_config)
        
        # Should have code blocks for commands
        assert "```" in readme
    
    def test_includes_links(self, sample_config):
        """Test that README includes helpful links."""
        readme = render_readme(sample_config)
        
        # Should include links to The Graph docs
        assert "thegraph.com" in readme or "graph" in readme.lower()
    
    def test_generated_by_wizard(self, sample_config):
        """Test that README mentions being generated by the wizard."""
        readme = render_readme(sample_config)
        
        assert "Subgraph Wizard" in readme or "generated" in readme.lower()
