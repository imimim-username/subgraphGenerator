"""Tests for stub mapping generation."""

import pytest

from subgraph_wizard.config.model import SubgraphConfig, ContractConfig
from subgraph_wizard.generate.mappings_stub import (
    render_mapping_stub,
    render_all_mappings_stub,
    get_all_handlers_for_contract,
)


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

# Sample ABI with underscore parameter names
UNDERSCORE_ABI = [
    {
        "type": "event",
        "name": "TokenMinted",
        "inputs": [
            {"name": "token_id", "type": "uint256", "indexed": True},
            {"name": "owner_address", "type": "address", "indexed": False},
        ],
    },
]


@pytest.fixture
def sample_contract():
    """Create a sample ContractConfig for testing."""
    return ContractConfig(
        name="TestToken",
        address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
        start_block=12345678,
        abi_path="TestToken.json",
    )


@pytest.fixture
def sample_config(tmp_path, sample_contract):
    """Create a sample SubgraphConfig for testing."""
    return SubgraphConfig(
        name="test-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "generated"),
        mappings_mode="stub",
        contracts=[sample_contract],
    )


@pytest.fixture
def multi_contract_config(tmp_path):
    """Create a config with multiple contracts."""
    return SubgraphConfig(
        name="multi-subgraph",
        network="ethereum",
        output_dir=str(tmp_path / "generated"),
        mappings_mode="stub",
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


class TestRenderMappingStubWithAbi:
    """Tests for stub mapping rendering with ABI data."""
    
    def test_generates_handler_function(self, sample_contract):
        """Test that handler function is generated from ABI event."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Should have handler function
        assert "export function handleTransfer" in mapping
    
    def test_handler_has_correct_event_type(self, sample_contract):
        """Test that handler has correct event type parameter."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Event type should be named after the event with 'Event' suffix
        assert "event: TransferEvent" in mapping
    
    def test_handler_contains_todo_comment(self, sample_contract):
        """Test that stub handler contains TODO comment."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Should contain TODO comment
        assert "TODO:" in mapping
    
    def test_handler_contains_example_entity_creation(self, sample_contract):
        """Test that stub handler contains commented example code."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Should have commented example for entity creation
        assert "// let entity = new Transfer(" in mapping or "//   let entity = new Transfer(" in mapping
    
    def test_handler_contains_example_params(self, sample_contract):
        """Test that stub handler contains commented parameter assignments."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Should have commented examples for setting parameters
        assert "// entity.from = event.params.from" in mapping or "//   entity.from = event.params.from" in mapping
        assert "// entity.to = event.params.to" in mapping or "//   entity.to = event.params.to" in mapping
        assert "// entity.value = event.params.value" in mapping or "//   entity.value = event.params.value" in mapping
    
    def test_handler_contains_example_metadata(self, sample_contract):
        """Test that stub handler contains commented metadata field examples."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Should have commented examples for metadata fields
        assert "// entity.blockNumber = event.block.number" in mapping or "//   entity.blockNumber = event.block.number" in mapping
        assert "// entity.blockTimestamp = event.block.timestamp" in mapping or "//   entity.blockTimestamp = event.block.timestamp" in mapping
        assert "// entity.transactionHash = event.transaction.hash" in mapping or "//   entity.transactionHash = event.transaction.hash" in mapping
    
    def test_handler_contains_example_save(self, sample_contract):
        """Test that stub handler contains commented save example."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Should have commented save call
        assert "// entity.save()" in mapping or "//   entity.save()" in mapping
    
    def test_generates_multiple_handlers(self, sample_contract):
        """Test that multiple events generate multiple handlers."""
        mapping = render_mapping_stub(sample_contract, "ethereum", MULTI_EVENT_ABI)
        
        assert "export function handleTransfer" in mapping
        assert "export function handleApproval" in mapping
    
    def test_generates_imports(self, sample_contract):
        """Test that correct imports are generated."""
        mapping = render_mapping_stub(sample_contract, "ethereum", TRANSFER_ABI)
        
        # Should import event type from generated contract types
        assert "Transfer as TransferEvent" in mapping
        # Should import entity from schema
        assert "import { Transfer }" in mapping or "Transfer" in mapping


class TestRenderMappingStubParameterNaming:
    """Tests for parameter naming in stub mappings."""
    
    def test_camel_cases_underscore_params(self, sample_contract):
        """Test that underscore params are converted to camelCase."""
        mapping = render_mapping_stub(sample_contract, "ethereum", UNDERSCORE_ABI)
        
        # Entity fields in comments should be camelCase
        assert "tokenId" in mapping
        assert "ownerAddress" in mapping


class TestRenderAllMappingsStub:
    """Tests for rendering stub mappings for all contracts."""
    
    def test_generates_mappings_for_all_contracts(self, multi_contract_config):
        """Test that mappings are generated for all contracts."""
        abi_map = {
            "TokenA": TRANSFER_ABI,
            "TokenB": MULTI_EVENT_ABI,
        }
        
        mappings = render_all_mappings_stub(multi_contract_config, abi_map)
        
        assert "TokenA" in mappings
        assert "TokenB" in mappings
        assert len(mappings) == 2
    
    def test_each_mapping_has_handlers(self, multi_contract_config):
        """Test that each mapping has appropriate handlers."""
        abi_map = {
            "TokenA": TRANSFER_ABI,
            "TokenB": MULTI_EVENT_ABI,
        }
        
        mappings = render_all_mappings_stub(multi_contract_config, abi_map)
        
        # TokenA should have Transfer handler
        assert "handleTransfer" in mappings["TokenA"]
        
        # TokenB should have Transfer and Approval handlers
        assert "handleTransfer" in mappings["TokenB"]
        assert "handleApproval" in mappings["TokenB"]
    
    def test_each_mapping_contains_todos(self, multi_contract_config):
        """Test that each mapping contains TODO comments."""
        abi_map = {
            "TokenA": TRANSFER_ABI,
            "TokenB": MULTI_EVENT_ABI,
        }
        
        mappings = render_all_mappings_stub(multi_contract_config, abi_map)
        
        assert "TODO:" in mappings["TokenA"]
        assert "TODO:" in mappings["TokenB"]


class TestRenderMappingStubWithoutAbi:
    """Tests for stub mapping rendering without ABI data."""
    
    def test_generates_placeholder_without_abi(self, sample_contract):
        """Test that placeholder handler is generated without ABI."""
        mapping = render_mapping_stub(sample_contract, "ethereum", None)
        
        # Should have placeholder handler
        assert "handleTestTokenEvent" in mapping
    
    def test_placeholder_has_todo_comment(self, sample_contract):
        """Test that placeholder handler has TODO comment."""
        mapping = render_mapping_stub(sample_contract, "ethereum", None)
        
        assert "TODO:" in mapping
    
    def test_placeholder_has_basic_params(self, sample_contract):
        """Test that placeholder handler has basic params in comments."""
        mapping = render_mapping_stub(sample_contract, "ethereum", None)
        
        # Should have sender and value params in comments
        assert "sender" in mapping
        assert "value" in mapping


class TestGetAllHandlersForContractStub:
    """Tests for get_all_handlers_for_contract function."""
    
    def test_returns_handlers_from_abi(self):
        """Test that handlers are extracted from ABI."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=0,
            abi_path="test.json",
        )
        
        handlers = get_all_handlers_for_contract(contract, MULTI_EVENT_ABI)
        
        assert len(handlers) == 2
        
        handler_names = [h["handler_name"] for h in handlers]
        assert "handleTransfer" in handler_names
        assert "handleApproval" in handler_names
        
        # Check event signatures
        signatures = [h["event_signature"] for h in handlers]
        assert "Transfer(address,address,uint256)" in signatures
        assert "Approval(address,address,uint256)" in signatures
    
    def test_returns_placeholder_without_abi(self):
        """Test that placeholder handler is returned without ABI."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=0,
            abi_path="test.json",
        )
        
        handlers = get_all_handlers_for_contract(contract, None)
        
        assert len(handlers) == 1
        assert handlers[0]["handler_name"] == "handleTestTokenEvent"
        assert handlers[0]["event_signature"] == "TestTokenEvent(address,uint256)"
    
    def test_returns_placeholder_with_no_events(self):
        """Test that placeholder is returned if ABI has no events."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=0,
            abi_path="test.json",
        )
        
        # ABI with only functions
        abi_no_events = [{"type": "function", "name": "transfer"}]
        
        handlers = get_all_handlers_for_contract(contract, abi_no_events)
        
        assert len(handlers) == 1
        assert handlers[0]["handler_name"] == "handleTestTokenEvent"
