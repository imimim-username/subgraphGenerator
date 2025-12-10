"""Tests for advanced complexity mapping generation.

Tests the generation of TypeScript mapping files with template instantiation
code and dynamic data source support.
"""

import pytest

from subgraph_wizard.config.model import (
    SubgraphConfig,
    ContractConfig,
    TemplateConfig,
)
from subgraph_wizard.generate.mappings_auto import (
    render_mapping_auto,
    render_all_mappings_auto,
    render_template_mapping_auto,
)
from subgraph_wizard.generate.mappings_stub import (
    render_mapping_stub,
    render_all_mappings_stub,
    render_template_mapping_stub,
)


def make_factory_contract():
    """Create a factory contract config for testing."""
    return ContractConfig(
        name="Factory",
        address="0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        start_block=10000835,
        abi_path="Factory.json",
        index_events=True,
    )


def make_pair_template():
    """Create a pair template config for testing."""
    return TemplateConfig(
        name="Pair",
        abi_path="Pair.json",
        event_handlers=["Swap", "Sync"],
        source_contract="Factory",
        source_event="PairCreated",
        index_events=True,
    )


def make_advanced_config():
    """Create an advanced subgraph config for testing."""
    return SubgraphConfig(
        name="uniswap-v2-subgraph",
        network="ethereum",
        output_dir="./output",
        mappings_mode="auto",
        contracts=[make_factory_contract()],
        config_version=3,
        complexity="advanced",
        templates=[make_pair_template()],
    )


# Sample ABIs for testing
FACTORY_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "token0", "type": "address"},
            {"indexed": True, "name": "token1", "type": "address"},
            {"indexed": False, "name": "pair", "type": "address"},
            {"indexed": False, "name": "pairId", "type": "uint256"},
        ],
        "name": "PairCreated",
        "type": "event",
    },
]

PAIR_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": False, "name": "amount0In", "type": "uint256"},
            {"indexed": False, "name": "amount1In", "type": "uint256"},
            {"indexed": False, "name": "amount0Out", "type": "uint256"},
            {"indexed": False, "name": "amount1Out", "type": "uint256"},
            {"indexed": True, "name": "to", "type": "address"},
        ],
        "name": "Swap",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "reserve0", "type": "uint112"},
            {"indexed": False, "name": "reserve1", "type": "uint112"},
        ],
        "name": "Sync",
        "type": "event",
    },
]


class TestAdvancedAutoMappings:
    """Tests for auto-generated mappings with advanced complexity."""
    
    def test_factory_mapping_includes_template_import(self):
        """Test that factory contract mapping imports template."""
        contract = make_factory_contract()
        templates = [make_pair_template()]
        
        result = render_mapping_auto(
            contract, "ethereum", FACTORY_ABI, "advanced", templates
        )
        
        assert "import { Pair } from" in result
        assert "../generated/templates" in result
    
    def test_factory_mapping_includes_template_creation(self):
        """Test that factory event handler includes template creation code."""
        contract = make_factory_contract()
        templates = [make_pair_template()]
        
        result = render_mapping_auto(
            contract, "ethereum", FACTORY_ABI, "advanced", templates
        )
        
        # Should have template creation code
        assert "Pair.create(" in result
        assert "event.params.pair" in result
    
    def test_render_all_mappings_includes_templates(self):
        """Test that render_all_mappings_auto includes template mappings."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_all_mappings_auto(config, abi_map)
        
        # Should have both Factory and Pair mappings
        assert "Factory" in result
        assert "Pair" in result
    
    def test_template_mapping_has_event_handlers(self):
        """Test that template mapping has event handlers."""
        template = make_pair_template()
        
        result = render_template_mapping_auto(template, "ethereum", PAIR_ABI)
        
        # Should have handlers for Swap and Sync
        assert "export function handleSwap(" in result
        assert "export function handleSync(" in result
    
    def test_template_mapping_creates_entities(self):
        """Test that template mapping creates entities from events."""
        template = make_pair_template()
        
        result = render_template_mapping_auto(template, "ethereum", PAIR_ABI)
        
        # Should create Swap and Sync entities
        assert "new Swap(" in result
        assert "new Sync(" in result
    
    def test_template_mapping_has_correct_imports(self):
        """Test that template mapping has correct imports."""
        template = make_pair_template()
        
        result = render_template_mapping_auto(template, "ethereum", PAIR_ABI)
        
        # Should import from generated/templates path
        assert "../generated/templates/Pair/Pair" in result
        assert "../generated/schema" in result
    
    def test_template_mapping_without_abi(self):
        """Test that template mapping works without ABI (uses placeholders)."""
        template = make_pair_template()
        
        result = render_template_mapping_auto(template, "ethereum", None)
        
        # Should still have handlers based on event_handlers list
        assert "export function handleSwap(" in result
        assert "export function handleSync(" in result
    
    def test_no_template_code_for_basic_complexity(self):
        """Test that basic complexity doesn't include template code."""
        contract = make_factory_contract()
        templates = [make_pair_template()]
        
        result = render_mapping_auto(
            contract, "ethereum", FACTORY_ABI, "basic", templates
        )
        
        # Should NOT have template import or creation
        assert "import { Pair } from" not in result
        assert "Pair.create(" not in result


class TestAdvancedStubMappings:
    """Tests for stub mappings with advanced complexity."""
    
    def test_factory_stub_includes_template_import(self):
        """Test that factory contract stub mapping imports template."""
        contract = make_factory_contract()
        templates = [make_pair_template()]
        
        result = render_mapping_stub(
            contract, "ethereum", FACTORY_ABI, "advanced", templates
        )
        
        assert "import { Pair } from" in result
        assert "../generated/templates" in result
    
    def test_factory_stub_includes_commented_template_creation(self):
        """Test that factory stub has commented template creation code."""
        contract = make_factory_contract()
        templates = [make_pair_template()]
        
        result = render_mapping_stub(
            contract, "ethereum", FACTORY_ABI, "advanced", templates
        )
        
        # Should have commented template creation code
        assert "// Pair.create(" in result or "Pair.create(" in result
    
    def test_render_all_stubs_includes_templates(self):
        """Test that render_all_mappings_stub includes template mappings."""
        config = make_advanced_config()
        config.mappings_mode = "stub"
        
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_all_mappings_stub(config, abi_map)
        
        # Should have both Factory and Pair mappings
        assert "Factory" in result
        assert "Pair" in result
    
    def test_template_stub_has_todo_comments(self):
        """Test that template stub has TODO comments."""
        template = make_pair_template()
        
        result = render_template_mapping_stub(template, "ethereum", PAIR_ABI)
        
        # Should have TODO comments
        assert "TODO" in result
    
    def test_template_stub_has_event_handlers(self):
        """Test that template stub has event handlers."""
        template = make_pair_template()
        
        result = render_template_mapping_stub(template, "ethereum", PAIR_ABI)
        
        # Should have handlers for Swap and Sync
        assert "export function handleSwap(" in result
        assert "export function handleSync(" in result


class TestTemplateWithCallAndBlockHandlers:
    """Tests for templates with call and block handlers."""
    
    def test_template_auto_with_call_handlers(self):
        """Test template auto mapping with call handlers."""
        template = TemplateConfig(
            name="Pair",
            abi_path="Pair.json",
            event_handlers=["Swap"],
            source_contract="Factory",
            source_event="PairCreated",
            call_handlers=["swap(uint256,uint256,address,bytes)"],
        )
        
        result = render_template_mapping_auto(template, "ethereum", PAIR_ABI)
        
        # Should have call handler
        assert "handleSwapCall" in result
    
    def test_template_auto_with_block_handler(self):
        """Test template auto mapping with block handler."""
        template = TemplateConfig(
            name="Pair",
            abi_path="Pair.json",
            event_handlers=["Swap"],
            source_contract="Factory",
            source_event="PairCreated",
            block_handler=True,
        )
        
        result = render_template_mapping_auto(template, "ethereum", PAIR_ABI)
        
        # Should have block handler
        assert "handlePairBlock" in result
    
    def test_template_stub_with_call_handlers(self):
        """Test template stub mapping with call handlers."""
        template = TemplateConfig(
            name="Pair",
            abi_path="Pair.json",
            event_handlers=["Swap"],
            source_contract="Factory",
            source_event="PairCreated",
            call_handlers=["swap(uint256,uint256,address,bytes)"],
        )
        
        result = render_template_mapping_stub(template, "ethereum", PAIR_ABI)
        
        # Should have call handler
        assert "handleSwapCall" in result
    
    def test_template_stub_with_block_handler(self):
        """Test template stub mapping with block handler."""
        template = TemplateConfig(
            name="Pair",
            abi_path="Pair.json",
            event_handlers=["Swap"],
            source_contract="Factory",
            source_event="PairCreated",
            block_handler=True,
        )
        
        result = render_template_mapping_stub(template, "ethereum", PAIR_ABI)
        
        # Should have block handler
        assert "handlePairBlock" in result
