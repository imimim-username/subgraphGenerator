"""Tests for advanced complexity subgraph.yaml generation.

Tests the generation of subgraph.yaml manifests with templates and
dynamic data sources for advanced complexity configurations.
"""

import pytest
import yaml

from subgraph_wizard.config.model import (
    SubgraphConfig,
    ContractConfig,
    TemplateConfig,
    EntityRelationship,
)
from subgraph_wizard.generate.subgraph_yaml import render_subgraph_yaml


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
        event_handlers=["Swap", "Sync", "Mint", "Burn"],
        source_contract="Factory",
        source_event="PairCreated",
        index_events=True,
    )


def make_advanced_config(
    templates=None,
    entity_relationships=None,
):
    """Create an advanced subgraph config for testing."""
    contracts = [make_factory_contract()]
    if templates is None:
        templates = [make_pair_template()]
    if entity_relationships is None:
        entity_relationships = []
    
    return SubgraphConfig(
        name="uniswap-v2-subgraph",
        network="ethereum",
        output_dir="./output",
        mappings_mode="auto",
        contracts=contracts,
        config_version=3,
        complexity="advanced",
        templates=templates,
        entity_relationships=entity_relationships,
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
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": False, "name": "amount0", "type": "uint256"},
            {"indexed": False, "name": "amount1", "type": "uint256"},
        ],
        "name": "Mint",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": False, "name": "amount0", "type": "uint256"},
            {"indexed": False, "name": "amount1", "type": "uint256"},
            {"indexed": True, "name": "to", "type": "address"},
        ],
        "name": "Burn",
        "type": "event",
    },
]


class TestAdvancedSubgraphYaml:
    """Tests for advanced complexity subgraph.yaml generation."""
    
    def test_renders_templates_section(self):
        """Test that templates section is rendered for advanced complexity."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        assert "templates" in parsed
        assert len(parsed["templates"]) == 1
    
    def test_template_has_correct_structure(self):
        """Test that template has required subgraph.yaml fields."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        template = parsed["templates"][0]
        
        assert template["kind"] == "ethereum"
        assert template["name"] == "Pair"
        assert template["network"] == "ethereum"
        assert "source" in template
        assert template["source"]["abi"] == "Pair"
        assert "mapping" in template
    
    def test_template_has_event_handlers(self):
        """Test that template has event handlers from ABI."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        template = parsed["templates"][0]
        mapping = template["mapping"]
        
        assert "eventHandlers" in mapping
        event_handlers = mapping["eventHandlers"]
        
        # Should have handlers for Swap, Sync, Mint, Burn
        handler_names = [h["handler"] for h in event_handlers]
        assert "handleSwap" in handler_names
        assert "handleSync" in handler_names
        assert "handleMint" in handler_names
        assert "handleBurn" in handler_names
    
    def test_template_has_entities(self):
        """Test that template has entities listed."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        template = parsed["templates"][0]
        mapping = template["mapping"]
        
        assert "entities" in mapping
        entities = mapping["entities"]
        
        # Should have entities for Swap, Sync, Mint, Burn
        assert "Swap" in entities
        assert "Sync" in entities
        assert "Mint" in entities
        assert "Burn" in entities
    
    def test_template_has_abi_reference(self):
        """Test that template has ABI reference in mapping."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        template = parsed["templates"][0]
        mapping = template["mapping"]
        
        assert "abis" in mapping
        abis = mapping["abis"]
        
        assert len(abis) == 1
        assert abis[0]["name"] == "Pair"
        assert abis[0]["file"] == "./abis/Pair.json"
    
    def test_template_has_mapping_file_reference(self):
        """Test that template has mapping file reference."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        template = parsed["templates"][0]
        mapping = template["mapping"]
        
        assert mapping["file"] == "./src/mappings/Pair.ts"
    
    def test_factory_contract_includes_template_abi(self):
        """Test that factory contract includes template ABI for import."""
        config = make_advanced_config()
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        factory = parsed["dataSources"][0]
        mapping = factory["mapping"]
        
        # Factory mapping should include Pair ABI for template instantiation
        abis = mapping["abis"]
        abi_names = [a["name"] for a in abis]
        
        assert "Factory" in abi_names
        assert "Pair" in abi_names
    
    def test_no_templates_section_for_basic_complexity(self):
        """Test that templates section is not rendered for basic complexity."""
        config = SubgraphConfig(
            name="basic-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[make_factory_contract()],
            config_version=1,
            complexity="basic",
            templates=[make_pair_template()],  # Templates present but complexity is basic
        )
        
        result = render_subgraph_yaml(config, {"Factory": FACTORY_ABI})
        parsed = yaml.safe_load(result)
        
        assert "templates" not in parsed or parsed.get("templates") is None
    
    def test_multiple_templates(self):
        """Test rendering with multiple templates."""
        # Create a second template for a different contract type
        second_template = TemplateConfig(
            name="LendingPool",
            abi_path="LendingPool.json",
            event_handlers=["Borrow", "Repay"],
            source_contract="Factory",
            source_event="PoolCreated",
            index_events=True,
        )
        
        config = make_advanced_config(templates=[make_pair_template(), second_template])
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        assert "templates" in parsed
        assert len(parsed["templates"]) == 2
        
        template_names = [t["name"] for t in parsed["templates"]]
        assert "Pair" in template_names
        assert "LendingPool" in template_names
    
    def test_template_with_call_handlers(self):
        """Test template with call handlers."""
        template = TemplateConfig(
            name="Pair",
            abi_path="Pair.json",
            event_handlers=["Swap"],
            source_contract="Factory",
            source_event="PairCreated",
            call_handlers=["swap(uint256,uint256,address,bytes)"],
        )
        
        config = make_advanced_config(templates=[template])
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        template_yaml = parsed["templates"][0]
        mapping = template_yaml["mapping"]
        
        assert "callHandlers" in mapping
        assert len(mapping["callHandlers"]) == 1
        assert mapping["callHandlers"][0]["handler"] == "handleSwapCall"
    
    def test_template_with_block_handler(self):
        """Test template with block handler."""
        template = TemplateConfig(
            name="Pair",
            abi_path="Pair.json",
            event_handlers=["Swap"],
            source_contract="Factory",
            source_event="PairCreated",
            block_handler=True,
        )
        
        config = make_advanced_config(templates=[template])
        abi_map = {
            "Factory": FACTORY_ABI,
            "Pair": PAIR_ABI,
        }
        
        result = render_subgraph_yaml(config, abi_map)
        parsed = yaml.safe_load(result)
        
        template_yaml = parsed["templates"][0]
        mapping = template_yaml["mapping"]
        
        assert "blockHandlers" in mapping
        assert len(mapping["blockHandlers"]) == 1
        assert mapping["blockHandlers"][0]["handler"] == "handlePairBlock"
    
    def test_advanced_config_without_abi(self):
        """Test that advanced config works without ABIs (uses placeholders)."""
        config = make_advanced_config()
        
        # No ABIs provided
        result = render_subgraph_yaml(config, None)
        parsed = yaml.safe_load(result)
        
        # Should still have templates section
        assert "templates" in parsed
        assert len(parsed["templates"]) == 1
        
        # Template should have event handlers based on event_handlers list
        template = parsed["templates"][0]
        mapping = template["mapping"]
        handler_names = [h["handler"] for h in mapping.get("eventHandlers", [])]
        
        assert "handleSwap" in handler_names
        assert "handleSync" in handler_names
