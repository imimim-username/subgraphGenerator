"""Tests for extract_read_functions() in abi/utils.py."""

import pytest
from subgraph_wizard.abi.utils import extract_read_functions

# ---------------------------------------------------------------------------
# Sample ABIs
# ---------------------------------------------------------------------------

SIMPLE_VIEW_ABI = [
    {
        "type": "function",
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    }
]

PURE_FUNCTION_ABI = [
    {
        "type": "function",
        "name": "decimals",
        "stateMutability": "pure",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    }
]

LEGACY_CONSTANT_ABI = [
    {
        "type": "function",
        "name": "symbol",
        "constant": True,
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    }
]

WRITE_FUNCTION_ABI = [
    {
        "type": "function",
        "name": "transfer",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    }
]

MULTI_OUTPUT_ABI = [
    {
        "type": "function",
        "name": "getReserves",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"},
        ],
    }
]

MIXED_ABI = [
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
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "transfer",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractReadFunctions:
    """Tests for extract_read_functions()."""

    def test_extracts_view_function(self):
        """view functions are returned."""
        fns = extract_read_functions(SIMPLE_VIEW_ABI)
        assert len(fns) == 1
        assert fns[0]["name"] == "balanceOf"

    def test_extracts_pure_function(self):
        """pure functions are returned."""
        fns = extract_read_functions(PURE_FUNCTION_ABI)
        assert len(fns) == 1
        assert fns[0]["name"] == "decimals"

    def test_extracts_legacy_constant_function(self):
        """Functions with constant=True are returned."""
        fns = extract_read_functions(LEGACY_CONSTANT_ABI)
        assert len(fns) == 1
        assert fns[0]["name"] == "symbol"

    def test_ignores_write_functions(self):
        """nonpayable / payable functions are excluded."""
        fns = extract_read_functions(WRITE_FUNCTION_ABI)
        assert fns == []

    def test_ignores_events(self):
        """Event entries are excluded."""
        fns = extract_read_functions(MIXED_ABI)
        assert len(fns) == 1
        assert fns[0]["name"] == "balanceOf"

    def test_returns_empty_for_no_read_functions(self):
        """Returns empty list when ABI has no read functions."""
        fns = extract_read_functions(WRITE_FUNCTION_ABI)
        assert fns == []

    def test_input_params_extracted(self):
        """Input parameters are correctly mapped."""
        fns = extract_read_functions(SIMPLE_VIEW_ABI)
        inputs = fns[0]["inputs"]
        assert len(inputs) == 1
        assert inputs[0]["name"] == "account"
        assert inputs[0]["solidity_type"] == "address"
        assert inputs[0]["graph_type"] == "Address"

    def test_output_params_extracted(self):
        """Output parameters are correctly mapped."""
        fns = extract_read_functions(SIMPLE_VIEW_ABI)
        outputs = fns[0]["outputs"]
        assert len(outputs) == 1
        assert outputs[0]["solidity_type"] == "uint256"
        assert outputs[0]["graph_type"] == "BigInt"

    def test_multiple_outputs(self):
        """Functions with multiple outputs are handled."""
        fns = extract_read_functions(MULTI_OUTPUT_ABI)
        assert len(fns) == 1
        outputs = fns[0]["outputs"]
        assert len(outputs) == 3
        assert outputs[0]["name"] == "reserve0"
        assert outputs[1]["name"] == "reserve1"
        assert outputs[2]["name"] == "blockTimestampLast"

    def test_no_inputs_function(self):
        """Functions with no inputs have empty inputs list."""
        fns = extract_read_functions(PURE_FUNCTION_ABI)
        assert fns[0]["inputs"] == []

    def test_signature_with_inputs(self):
        """Signature includes input types."""
        fns = extract_read_functions(SIMPLE_VIEW_ABI)
        assert fns[0]["signature"] == "balanceOf(address)"

    def test_signature_no_inputs(self):
        """Signature with no inputs has empty parens."""
        fns = extract_read_functions(PURE_FUNCTION_ABI)
        assert fns[0]["signature"] == "decimals()"

    def test_unnamed_output_gets_generated_name(self):
        """Unnamed output parameters get a generated name (param0, etc.)."""
        fns = extract_read_functions(SIMPLE_VIEW_ABI)
        # Output name is empty string "" in ABI → should become "param0"
        assert fns[0]["outputs"][0]["name"] == "param0"

    def test_empty_abi_returns_empty(self):
        """Empty ABI list returns empty list."""
        assert extract_read_functions([]) == []
