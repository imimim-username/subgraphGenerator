"""Tests for ABI source loading (local file and paste)."""

import pytest
import json
from pathlib import Path

from subgraph_wizard.abi.local import load_abi_from_file, write_abi_to_file
from subgraph_wizard.abi.paste import load_abi_from_paste
from subgraph_wizard.abi.utils import (
    parse_abi,
    validate_abi,
    extract_events,
    solidity_type_to_graph,
    build_event_signature,
    get_handler_name,
    get_entity_name,
    to_camel_case,
)
from subgraph_wizard.errors import ValidationError, AbiFetchError


# Sample valid ABI with one event (ERC20 Transfer)
SAMPLE_ABI = [
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
        "type": "function",
        "name": "transfer",
        "inputs": [
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"type": "bool"}],
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


class TestParseAbi:
    """Tests for parse_abi function."""
    
    def test_parses_json_string(self):
        """Test parsing ABI from JSON string."""
        json_str = json.dumps(SAMPLE_ABI)
        result = parse_abi(json_str)
        assert result == SAMPLE_ABI
    
    def test_parses_list_directly(self):
        """Test parsing ABI when already a list."""
        result = parse_abi(SAMPLE_ABI)
        assert result == SAMPLE_ABI
    
    def test_raises_on_invalid_json(self):
        """Test that invalid JSON raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid ABI JSON"):
            parse_abi("not valid json {{{")
    
    def test_raises_on_non_array_json(self):
        """Test that non-array JSON raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a JSON array"):
            parse_abi('{"type": "event"}')


class TestValidateAbi:
    """Tests for validate_abi function."""
    
    def test_valid_abi_passes(self):
        """Test that valid ABI passes validation."""
        # Should not raise
        validate_abi(SAMPLE_ABI)
    
    def test_raises_on_non_list(self):
        """Test that non-list raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a list"):
            validate_abi({"type": "event"})
    
    def test_raises_on_empty_list(self):
        """Test that empty list raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_abi([])
    
    def test_raises_on_non_dict_entry(self):
        """Test that non-dict entry raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a dictionary"):
            validate_abi(["not a dict"])
    
    def test_raises_on_missing_type(self):
        """Test that entry without type raises ValidationError."""
        with pytest.raises(ValidationError, match="missing 'type' field"):
            validate_abi([{"name": "Transfer"}])


class TestSolidityTypeToGraph:
    """Tests for Solidity to Graph type conversion."""
    
    def test_address_to_bytes(self):
        assert solidity_type_to_graph("address") == "Bytes"
    
    def test_uint256_to_bigint(self):
        assert solidity_type_to_graph("uint256") == "BigInt"
    
    def test_uint8_to_int(self):
        assert solidity_type_to_graph("uint8") == "Int"
    
    def test_bool_to_boolean(self):
        assert solidity_type_to_graph("bool") == "Boolean"
    
    def test_string_to_string(self):
        assert solidity_type_to_graph("string") == "String"
    
    def test_bytes32_to_bytes(self):
        assert solidity_type_to_graph("bytes32") == "Bytes"
    
    def test_array_type(self):
        assert solidity_type_to_graph("address[]") == "[Bytes!]"
    
    def test_fixed_array_type(self):
        assert solidity_type_to_graph("uint256[10]") == "[BigInt!]"


class TestExtractEvents:
    """Tests for extract_events function."""
    
    def test_extracts_single_event(self):
        """Test extracting a single event from ABI."""
        events = extract_events(SAMPLE_ABI)
        
        assert len(events) == 1
        assert events[0]["name"] == "Transfer"
        assert len(events[0]["params"]) == 3
    
    def test_extracts_multiple_events(self):
        """Test extracting multiple events from ABI."""
        events = extract_events(MULTI_EVENT_ABI)
        
        assert len(events) == 2
        event_names = [e["name"] for e in events]
        assert "Transfer" in event_names
        assert "Approval" in event_names
    
    def test_extracts_event_params(self):
        """Test that event parameters are correctly extracted."""
        events = extract_events(SAMPLE_ABI)
        
        params = events[0]["params"]
        assert params[0]["name"] == "from"
        assert params[0]["solidity_type"] == "address"
        assert params[0]["graph_type"] == "Bytes"
        assert params[0]["indexed"] is True
        
        assert params[2]["name"] == "value"
        assert params[2]["solidity_type"] == "uint256"
        assert params[2]["graph_type"] == "BigInt"
        assert params[2]["indexed"] is False
    
    def test_ignores_non_events(self):
        """Test that functions are ignored."""
        events = extract_events(SAMPLE_ABI)
        
        # Should only have 1 event, not the function
        assert len(events) == 1
        assert events[0]["name"] == "Transfer"
    
    def test_builds_event_signature(self):
        """Test that event signature is built correctly."""
        events = extract_events(SAMPLE_ABI)
        
        assert events[0]["signature"] == "Transfer(address,address,uint256)"


class TestBuildEventSignature:
    """Tests for build_event_signature function."""
    
    def test_simple_signature(self):
        inputs = [{"type": "address"}, {"type": "uint256"}]
        sig = build_event_signature("Transfer", inputs)
        assert sig == "Transfer(address,uint256)"
    
    def test_empty_inputs(self):
        sig = build_event_signature("Pause", [])
        assert sig == "Pause()"
    
    def test_indexed_parameters(self):
        """Test that indexed parameters are correctly formatted as 'indexed type'."""
        inputs = [
            {"type": "address", "indexed": True},
            {"type": "address", "indexed": True},
            {"type": "uint256", "indexed": False}
        ]
        sig = build_event_signature("Transfer", inputs)
        assert sig == "Transfer(indexed address,indexed address,uint256)"
    
    def test_mixed_indexed_and_non_indexed(self):
        """Test events with mixed indexed and non-indexed parameters."""
        inputs = [
            {"type": "address", "indexed": True},
            {"type": "uint256", "indexed": False}
        ]
        sig = build_event_signature("BeaconUpgraded", inputs)
        assert sig == "BeaconUpgraded(indexed address,uint256)"


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_get_handler_name(self):
        assert get_handler_name("Transfer") == "handleTransfer"
        assert get_handler_name("Approval") == "handleApproval"
    
    def test_get_entity_name(self):
        assert get_entity_name("Transfer") == "Transfer"
        assert get_entity_name("Approval") == "Approval"
    
    def test_to_camel_case(self):
        assert to_camel_case("token_id") == "tokenId"
        assert to_camel_case("from") == "from"
        assert to_camel_case("my_cool_variable") == "myCoolVariable"
        assert to_camel_case("") == ""


class TestLoadAbiFromFile:
    """Tests for load_abi_from_file function."""
    
    def test_loads_valid_abi_file(self, tmp_path):
        """Test loading a valid ABI from file."""
        abi_file = tmp_path / "test.json"
        abi_file.write_text(json.dumps(SAMPLE_ABI))
        
        result = load_abi_from_file(abi_file)
        assert result == SAMPLE_ABI
    
    def test_raises_on_nonexistent_file(self, tmp_path):
        """Test that nonexistent file raises AbiFetchError."""
        with pytest.raises(AbiFetchError, match="not found"):
            load_abi_from_file(tmp_path / "nonexistent.json")
    
    def test_raises_on_directory(self, tmp_path):
        """Test that directory raises AbiFetchError."""
        with pytest.raises(AbiFetchError, match="not a file"):
            load_abi_from_file(tmp_path)
    
    def test_raises_on_empty_file(self, tmp_path):
        """Test that empty file raises ValidationError."""
        abi_file = tmp_path / "empty.json"
        abi_file.write_text("")
        
        with pytest.raises(ValidationError, match="empty"):
            load_abi_from_file(abi_file)
    
    def test_raises_on_invalid_json_file(self, tmp_path):
        """Test that invalid JSON file raises ValidationError."""
        abi_file = tmp_path / "invalid.json"
        abi_file.write_text("not json {{{")
        
        with pytest.raises(ValidationError, match="Invalid JSON"):
            load_abi_from_file(abi_file)
    
    def test_raises_on_non_array_json_file(self, tmp_path):
        """Test that non-array JSON file raises ValidationError."""
        abi_file = tmp_path / "object.json"
        abi_file.write_text('{"type": "event"}')
        
        with pytest.raises(ValidationError, match="must be a JSON array"):
            load_abi_from_file(abi_file)


class TestWriteAbiToFile:
    """Tests for write_abi_to_file function."""
    
    def test_writes_abi_file(self, tmp_path):
        """Test writing ABI to file."""
        abi_file = tmp_path / "output.json"
        write_abi_to_file(SAMPLE_ABI, abi_file)
        
        assert abi_file.exists()
        content = json.loads(abi_file.read_text())
        assert content == SAMPLE_ABI
    
    def test_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created."""
        abi_file = tmp_path / "subdir" / "nested" / "output.json"
        write_abi_to_file(SAMPLE_ABI, abi_file)
        
        assert abi_file.exists()


class TestLoadAbiFromPaste:
    """Tests for load_abi_from_paste function."""
    
    def test_loads_valid_pasted_json(self):
        """Test loading valid pasted ABI JSON."""
        json_text = json.dumps(SAMPLE_ABI)
        result = load_abi_from_paste(json_text)
        assert result == SAMPLE_ABI
    
    def test_handles_whitespace(self):
        """Test that whitespace is handled."""
        json_text = f"  \n{json.dumps(SAMPLE_ABI)}\n  "
        result = load_abi_from_paste(json_text)
        assert result == SAMPLE_ABI
    
    def test_raises_on_empty_input(self):
        """Test that empty input raises ValidationError."""
        with pytest.raises(ValidationError, match="No ABI content"):
            load_abi_from_paste("")
    
    def test_raises_on_whitespace_only(self):
        """Test that whitespace-only input raises ValidationError."""
        with pytest.raises(ValidationError, match="No ABI content"):
            load_abi_from_paste("   \n\t  ")
    
    def test_raises_on_invalid_json(self):
        """Test that invalid JSON raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid JSON"):
            load_abi_from_paste("not valid json")
    
    def test_raises_on_non_array_json(self):
        """Test that non-array JSON raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a JSON array"):
            load_abi_from_paste('{"type": "event"}')

