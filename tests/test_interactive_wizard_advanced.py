"""Tests for the interactive wizard (advanced complexity).

These tests validate the advanced complexity features of the wizard:
- Dynamic data source templates
- Entity relationships
- Advanced validators
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from subgraph_wizard.interactive_wizard import (
    run_wizard,
    _validate_template_name,
    _validate_event_name,
    _validate_entity_name,
    _validate_field_name,
    _collect_template,
    _collect_entity_relationship,
)
from subgraph_wizard.config.model import (
    SubgraphConfig,
    ContractConfig,
    TemplateConfig,
    EntityRelationship,
)
from subgraph_wizard.errors import ValidationError, AbiFetchError


# Sample ABI for testing
SAMPLE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

# Sample ABI for a Pair contract (dynamic data source)
PAIR_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "amount0", "type": "uint256"},
            {"indexed": False, "name": "amount1", "type": "uint256"}
        ],
        "name": "Swap",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "reserve0", "type": "uint112"},
            {"indexed": False, "name": "reserve1", "type": "uint112"}
        ],
        "name": "Sync",
        "type": "event"
    }
]


class TestAdvancedValidators:
    """Tests for advanced validation helper functions."""
    
    def test_validate_template_name_valid(self):
        """Valid template names should pass."""
        assert _validate_template_name("Pair")
        assert _validate_template_name("Pool")
        assert _validate_template_name("Vault_V2")
        assert _validate_template_name("A")
        assert _validate_template_name("PoolTemplate123")
    
    def test_validate_template_name_invalid(self):
        """Invalid template names should fail."""
        assert not _validate_template_name("")
        assert not _validate_template_name("123Pair")  # Starts with number
        assert not _validate_template_name("Pair-Template")  # Has hyphen
        assert not _validate_template_name("_Pair")  # Starts with underscore
        assert not _validate_template_name("Pair Template")  # Has space
    
    def test_validate_event_name_valid(self):
        """Valid event names should pass."""
        assert _validate_event_name("Transfer")
        assert _validate_event_name("Swap")
        assert _validate_event_name("PairCreated")
        assert _validate_event_name("Approval_V2")
    
    def test_validate_event_name_invalid(self):
        """Invalid event names should fail."""
        assert not _validate_event_name("")
        assert not _validate_event_name("123Transfer")
        assert not _validate_event_name("Transfer-Event")
        assert not _validate_event_name("Transfer Event")
    
    def test_validate_entity_name_valid(self):
        """Valid entity names should pass."""
        assert _validate_entity_name("Pool")
        assert _validate_entity_name("Factory")
        assert _validate_entity_name("Token_Holder")
        assert _validate_entity_name("SwapEvent")
    
    def test_validate_entity_name_invalid(self):
        """Invalid entity names should fail."""
        assert not _validate_entity_name("")
        assert not _validate_entity_name("123Pool")
        assert not _validate_entity_name("Pool-Entity")
        assert not _validate_entity_name("Pool Entity")
    
    def test_validate_field_name_valid(self):
        """Valid field names should pass."""
        assert _validate_field_name("factory")
        assert _validate_field_name("token0")
        assert _validate_field_name("reserve_amount")
        assert _validate_field_name("Factory")  # PascalCase also allowed
    
    def test_validate_field_name_invalid(self):
        """Invalid field names should fail."""
        assert not _validate_field_name("")
        assert not _validate_field_name("123field")
        assert not _validate_field_name("field-name")
        assert not _validate_field_name("field name")


class TestCollectTemplate:
    """Tests for _collect_template function."""
    
    def test_collect_template_basic(self, monkeypatch):
        """Test collecting a basic template configuration."""
        inputs = iter([
            "Pair",           # Template name
            "",               # ABI path (use default: Pair.json)
            "1",              # Select source contract (first one)
            "PairCreated",    # Source event
            "Swap",           # Event handler 1
            "Sync",           # Event handler 2
            "",               # End event handlers
            "y",              # Index all events
            "n",              # No call handlers
            "n",              # No block handler
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        template = _collect_template(set(), ["Factory"])
        
        assert template.name == "Pair"
        assert template.abi_path == "Pair.json"
        assert template.source_contract == "Factory"
        assert template.source_event == "PairCreated"
        assert "Swap" in template.event_handlers
        assert "Sync" in template.event_handlers
        assert template.index_events is True
        assert template.call_handlers is None
        assert template.block_handler is False
    
    def test_collect_template_with_call_handlers(self, monkeypatch):
        """Test collecting template with call handlers enabled."""
        inputs = iter([
            "Pool",              # Template name
            "Pool.json",         # ABI path
            "1",                 # Select source contract
            "PoolCreated",       # Source event
            "Swap",              # Event handler
            "",                  # End event handlers
            "y",                 # Index all events
            "y",                 # Enable call handlers
            "swap(uint256)",     # Call handler signature
            "",                  # End call handlers
            "n",                 # No block handler
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        template = _collect_template(set(), ["Factory"])
        
        assert template.name == "Pool"
        assert template.call_handlers == ["swap(uint256)"]
    
    def test_collect_template_duplicate_name_rejected(self, monkeypatch):
        """Test that duplicate template names are rejected."""
        inputs = iter([
            "Pair",        # First attempt (duplicate)
            "PairV2",      # Corrected name
            "",            # ABI path default
            "1",           # Source contract
            "PairCreated", # Source event
            "Swap",        # Event handler
            "",            # End event handlers
            "y",           # Index events
            "n",           # No call handlers
            "n",           # No block handler
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        template = _collect_template({"Pair"}, ["Factory"])
        
        assert template.name == "PairV2"


class TestCollectEntityRelationship:
    """Tests for _collect_entity_relationship function."""
    
    def test_collect_relationship_basic(self, monkeypatch):
        """Test collecting a basic entity relationship."""
        inputs = iter([
            "Pool",      # From entity
            "Factory",   # To entity
            "",          # Field name (use default: factory)
            "1",         # Relation type (one_to_one)
            "n",         # Not a derived field
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        relationship = _collect_entity_relationship([])
        
        assert relationship.from_entity == "Pool"
        assert relationship.to_entity == "Factory"
        assert relationship.field_name == "factory"
        assert relationship.relation_type == "one_to_one"
        assert relationship.derived_from is None
    
    def test_collect_relationship_with_derived_field(self, monkeypatch):
        """Test collecting a relationship with derived field."""
        inputs = iter([
            "Factory",   # From entity
            "Pool",      # To entity
            "pools",     # Field name
            "2",         # Relation type (one_to_many)
            "y",         # Is derived field
            "factory",   # Derived from field
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        relationship = _collect_entity_relationship([])
        
        assert relationship.from_entity == "Factory"
        assert relationship.to_entity == "Pool"
        assert relationship.field_name == "pools"
        assert relationship.relation_type == "one_to_many"
        assert relationship.derived_from == "factory"
    
    def test_collect_relationship_many_to_many(self, monkeypatch):
        """Test collecting a many-to-many relationship."""
        inputs = iter([
            "User",      # From entity
            "Token",     # To entity
            "tokens",    # Field name
            "3",         # Relation type (many_to_many)
            "n",         # Not derived
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        relationship = _collect_entity_relationship([])
        
        assert relationship.relation_type == "many_to_many"


class TestRunWizardAdvanced:
    """Tests for run_wizard with advanced complexity."""
    
    def test_run_wizard_advanced_without_templates(self, tmp_path, monkeypatch):
        """Test advanced mode wizard without adding templates or relationships."""
        output_dir = tmp_path / "advanced-subgraph"
        
        inputs = iter([
            "advanced-subgraph",        # Subgraph name
            "1",                        # Network choice (arbitrum)
            str(output_dir),            # Output directory
            "3",                        # Complexity choice (advanced)
            "1",                        # Mapping mode (auto)
            "Factory",                  # Contract name
            "0x1234567890123456789012345678901234567890",  # Contract address
            "12345678",                 # Start block
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),     # Pasted ABI
            "END",                      # End paste marker
            "n",                        # Don't add another contract
            "n",                        # Don't add templates
            "n",                        # Don't add relationships
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        assert config.name == "advanced-subgraph"
        assert config.complexity == "advanced"
        assert config.config_version == 3
        assert len(config.contracts) == 1
        assert len(config.templates) == 0
        assert len(config.entity_relationships) == 0
    
    def test_run_wizard_advanced_with_template(self, tmp_path, monkeypatch):
        """Test advanced mode wizard with a template."""
        output_dir = tmp_path / "factory-subgraph"
        
        inputs = iter([
            "factory-subgraph",         # Subgraph name
            "2",                        # Network choice (ethereum)
            str(output_dir),            # Output directory
            "3",                        # Complexity choice (advanced)
            "1",                        # Mapping mode (auto)
            "Factory",                  # Contract name
            "0x1111111111111111111111111111111111111111",  # Contract address
            "0",                        # Start block
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),     # Pasted ABI
            "END",                      # End paste marker
            "n",                        # Don't add another contract
            "y",                        # Add templates
            # Template configuration
            "Pair",                     # Template name
            "",                         # ABI path (default: Pair.json)
            "1",                        # Source contract (Factory)
            "PairCreated",              # Source event
            "Swap",                     # Event handler 1
            "",                         # End event handlers
            "y",                        # Index events
            "n",                        # No call handlers
            "n",                        # No block handler
            # Template ABI
            "2",                        # ABI source (paste JSON)
            json.dumps(PAIR_ABI),       # Pasted template ABI
            "END",                      # End paste marker
            "n",                        # Don't add another template
            "n",                        # Don't add relationships
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        assert config.complexity == "advanced"
        assert len(config.templates) == 1
        
        template = config.templates[0]
        assert template.name == "Pair"
        assert template.source_contract == "Factory"
        assert template.source_event == "PairCreated"
        assert "Swap" in template.event_handlers
        
        # Verify template ABI was written
        assert (output_dir / "abis" / "Pair.json").exists()
    
    def test_run_wizard_advanced_with_relationship(self, tmp_path, monkeypatch):
        """Test advanced mode wizard with an entity relationship."""
        output_dir = tmp_path / "relationship-subgraph"
        
        inputs = iter([
            "relationship-subgraph",    # Subgraph name
            "1",                        # Network choice
            str(output_dir),            # Output directory
            "3",                        # Complexity choice (advanced)
            "1",                        # Mapping mode (auto)
            "Factory",                  # Contract name
            "0x1111111111111111111111111111111111111111",  # Contract address
            "0",                        # Start block
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),     # Pasted ABI
            "END",                      # End paste marker
            "n",                        # Don't add another contract
            "n",                        # Don't add templates
            "y",                        # Add relationships
            # Relationship configuration
            "Pool",                     # From entity
            "Factory",                  # To entity
            "",                         # Field name (default: factory)
            "1",                        # Relation type (one_to_one)
            "n",                        # Not derived
            "n",                        # Don't add another relationship
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        assert config.complexity == "advanced"
        assert len(config.entity_relationships) == 1
        
        relationship = config.entity_relationships[0]
        assert relationship.from_entity == "Pool"
        assert relationship.to_entity == "Factory"
        assert relationship.field_name == "factory"
        assert relationship.relation_type == "one_to_one"
    
    def test_run_wizard_advanced_full_config(self, tmp_path, monkeypatch):
        """Test advanced wizard with templates and relationships."""
        output_dir = tmp_path / "full-advanced"
        
        inputs = iter([
            "full-advanced",            # Subgraph name
            "2",                        # Network choice (ethereum)
            str(output_dir),            # Output directory
            "3",                        # Complexity choice (advanced)
            "1",                        # Mapping mode (auto)
            # Contract 1 - Factory
            "Factory",                  # Contract name
            "0x1111111111111111111111111111111111111111",  # Contract address
            "100",                      # Start block
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),     # Pasted ABI
            "END",                      # End paste marker
            "n",                        # Don't add another contract
            # Templates
            "y",                        # Add templates
            "Pair",                     # Template name
            "",                         # ABI path (default)
            "1",                        # Source contract
            "PairCreated",              # Source event
            "Swap",                     # Event handler 1
            "Sync",                     # Event handler 2
            "",                         # End event handlers
            "y",                        # Index events
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source (paste)
            json.dumps(PAIR_ABI),       # Template ABI
            "END",                      # End paste
            "n",                        # Don't add another template
            # Relationships
            "y",                        # Add relationships
            "Pair",                     # From entity
            "Factory",                  # To entity
            "factory",                  # Field name
            "1",                        # Relation type (one_to_one)
            "n",                        # Not derived
            "y",                        # Add another relationship
            "Factory",                  # From entity
            "Pair",                     # To entity
            "pairs",                    # Field name
            "2",                        # Relation type (one_to_many)
            "y",                        # Is derived
            "factory",                  # Derived from
            "n",                        # Don't add another relationship
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        # Verify full configuration
        assert config.name == "full-advanced"
        assert config.complexity == "advanced"
        assert config.config_version == 3
        assert len(config.contracts) == 1
        assert len(config.templates) == 1
        assert len(config.entity_relationships) == 2
        
        # Verify template
        template = config.templates[0]
        assert template.name == "Pair"
        assert template.source_contract == "Factory"
        assert template.source_event == "PairCreated"
        assert set(template.event_handlers) == {"Swap", "Sync"}
        
        # Verify relationships
        rel1 = config.entity_relationships[0]
        assert rel1.from_entity == "Pair"
        assert rel1.to_entity == "Factory"
        
        rel2 = config.entity_relationships[1]
        assert rel2.from_entity == "Factory"
        assert rel2.to_entity == "Pair"
        assert rel2.derived_from == "factory"
        
        # Verify files created
        assert (output_dir / "subgraph-config.json").exists()
        assert (output_dir / "abis" / "Factory.json").exists()
        assert (output_dir / "abis" / "Pair.json").exists()
        
        # Verify config file content
        with open(output_dir / "subgraph-config.json") as f:
            saved_config = json.load(f)
        
        assert saved_config["complexity"] == "advanced"
        assert saved_config["config_version"] == 3
        assert "templates" in saved_config
        assert len(saved_config["templates"]) == 1
        assert "entity_relationships" in saved_config
        assert len(saved_config["entity_relationships"]) == 2
    
    def test_run_wizard_advanced_shows_summary(self, tmp_path, monkeypatch, capsys):
        """Test that advanced wizard shows proper summary output."""
        output_dir = tmp_path / "summary-test"
        
        inputs = iter([
            "summary-test",             # Subgraph name
            "1",                        # Network choice
            str(output_dir),            # Output directory
            "3",                        # Complexity choice (advanced)
            "1",                        # Mapping mode (auto)
            "Factory",                  # Contract name
            "0x1111111111111111111111111111111111111111",  # Contract address
            "0",                        # Start block
            "y",                        # Enable call handlers
            "transfer(address,uint256)", # Call handler
            "",                         # End call handlers
            "y",                        # Enable block handler
            "2",                        # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),     # Pasted ABI
            "END",                      # End paste marker
            "n",                        # Don't add another contract
            "y",                        # Add templates
            "Pair",                     # Template name
            "",                         # ABI path
            "1",                        # Source contract
            "PairCreated",              # Source event
            "Swap",                     # Event handler
            "",                         # End handlers
            "y",                        # Index events
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source
            json.dumps(PAIR_ABI),       # Template ABI
            "END",                      # End paste
            "n",                        # No more templates
            "n",                        # No relationships
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        config = run_wizard()
        
        captured = capsys.readouterr()
        
        # Verify summary shows advanced features
        assert "Complexity: advanced" in captured.out
        assert "Templates: 1" in captured.out
        assert "Pair" in captured.out
        assert "Factory.PairCreated" in captured.out
        # Verify handler summary
        assert "Contracts with call handlers: Factory" in captured.out
        assert "Contracts with block handlers: Factory" in captured.out


class TestAdvancedConfigSerialization:
    """Tests for advanced config serialization/deserialization."""
    
    def test_advanced_config_roundtrip(self, tmp_path, monkeypatch):
        """Test that advanced config survives save/load cycle."""
        output_dir = tmp_path / "roundtrip-test"
        
        inputs = iter([
            "roundtrip-test",           # Subgraph name
            "2",                        # Network choice (ethereum)
            str(output_dir),            # Output directory
            "3",                        # Complexity choice (advanced)
            "1",                        # Mapping mode (auto)
            "Factory",                  # Contract name
            "0x1111111111111111111111111111111111111111",  # Contract address
            "0",                        # Start block
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source (paste JSON)
            json.dumps(SAMPLE_ABI),     # Pasted ABI
            "END",                      # End paste marker
            "n",                        # Don't add another contract
            "y",                        # Add templates
            "Pool",                     # Template name
            "Pool.json",                # ABI path
            "1",                        # Source contract
            "PoolCreated",              # Source event
            "Swap",                     # Event handler
            "",                         # End handlers
            "y",                        # Index events
            "n",                        # No call handlers
            "n",                        # No block handler
            "2",                        # ABI source
            json.dumps(PAIR_ABI),       # Template ABI
            "END",                      # End paste
            "n",                        # No more templates
            "y",                        # Add relationships
            "Pool",                     # From entity
            "Factory",                  # To entity
            "factory",                  # Field name
            "1",                        # Relation type
            "n",                        # Not derived
            "n",                        # No more relationships
        ])
        
        def mock_input(prompt=""):
            return next(inputs)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        original_config = run_wizard()
        
        # Load the saved config
        from subgraph_wizard.config.io import load_config
        
        loaded_config = load_config(output_dir / "subgraph-config.json")
        
        # Compare configs
        assert loaded_config.name == original_config.name
        assert loaded_config.complexity == original_config.complexity
        assert loaded_config.config_version == original_config.config_version
        assert len(loaded_config.templates) == len(original_config.templates)
        assert len(loaded_config.entity_relationships) == len(original_config.entity_relationships)
        
        # Compare template details
        if loaded_config.templates:
            orig_template = original_config.templates[0]
            loaded_template = loaded_config.templates[0]
            assert loaded_template.name == orig_template.name
            assert loaded_template.source_contract == orig_template.source_contract
            assert loaded_template.source_event == orig_template.source_event
        
        # Compare relationship details
        if loaded_config.entity_relationships:
            orig_rel = original_config.entity_relationships[0]
            loaded_rel = loaded_config.entity_relationships[0]
            assert loaded_rel.from_entity == orig_rel.from_entity
            assert loaded_rel.to_entity == orig_rel.to_entity
            assert loaded_rel.relation_type == orig_rel.relation_type
