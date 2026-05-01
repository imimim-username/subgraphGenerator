"""Tests for get_contract_deployment_block — all API calls are mocked."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure ETHERSCAN_API_KEY is set for all tests so the early-exit guard
# doesn't trigger.
os.environ.setdefault("ETHERSCAN_API_KEY", "TEST_KEY")
os.environ.setdefault("OPTIMISM_ETHERSCAN_API_KEY", "TEST_OP_KEY")

from subgraph_wizard.abi.etherscan import get_contract_deployment_block  # noqa: E402

ADDR = "0xAf510a560744880410f0f65e3341A020FBC2cA41"
TX_HASH = "0xdeadbeef"


def _resp(payload: dict) -> MagicMock:
    """Build a mock requests.Response that returns *payload* as JSON."""
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = payload
    return m


# ── Helpers for common payloads ───────────────────────────────────────────────

def _creation_ok(block_number=None):
    """getcontractcreation success payload."""
    result = {"txHash": TX_HASH, "contractCreator": "0xabc"}
    if block_number is not None:
        result["blockNumber"] = block_number
    return {"status": "1", "message": "OK", "result": [result]}


def _creation_fail():
    return {"status": "0", "message": "NOTOK", "result": "Contract source code not verified"}


def _tx_ok(block_hex="0xc350"):  # 0xc350 == 50000
    return {"jsonrpc": "2.0", "result": {"blockNumber": block_hex, "hash": TX_HASH}, "id": 1}


def _tx_null():
    return {"jsonrpc": "2.0", "result": None, "id": 1}


def _txlist_ok(block_decimal="130000"):
    return {"status": "1", "result": [{"blockNumber": block_decimal, "hash": TX_HASH}]}


def _txlist_empty():
    return {"status": "0", "result": "No transactions found"}


# ── Step 1 failures ───────────────────────────────────────────────────────────

class TestStep1Failures:
    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        assert get_contract_deployment_block("mainnet", ADDR) is None

    def test_optimism_no_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("OPTIMISM_ETHERSCAN_API_KEY", raising=False)
        assert get_contract_deployment_block("optimism", ADDR) is None

    def test_unknown_network_returns_none(self):
        assert get_contract_deployment_block("not-a-real-net", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_api_error_returns_none(self, mock_get):
        mock_get.return_value = _resp(_creation_fail())
        assert get_contract_deployment_block("mainnet", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_request_exception_returns_none(self, mock_get):
        mock_get.side_effect = Exception("network error")
        assert get_contract_deployment_block("mainnet", ADDR) is None


class TestOptimismChainSpecificApi:
    """Optimism uses api-optimistic.etherscan.io, not the v2 unified API."""

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_optimism_uses_chain_specific_base_url(self, mock_get):
        mock_get.return_value = _resp(_creation_ok(block_number="130789234"))
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 130789234
        call_url = mock_get.call_args[0][0]
        assert "api-optimistic.etherscan.io" in call_url
        assert "v2" not in call_url
        assert "chainid" not in call_url

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_mainnet_uses_v2_unified_url(self, mock_get):
        mock_get.return_value = _resp(_creation_ok(block_number="24875892"))
        get_contract_deployment_block("mainnet", ADDR)
        call_url = mock_get.call_args[0][0]
        assert "api.etherscan.io/v2/api" in call_url
        assert "chainid=1" in call_url


# ── Step 1b: blockNumber in creation response ─────────────────────────────────

class TestStep1bBlockInCreationResponse:
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_decimal_block_in_creation_response(self, mock_get):
        mock_get.return_value = _resp(_creation_ok(block_number="24875892"))
        assert get_contract_deployment_block("mainnet", ADDR) == 24875892

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_hex_block_in_creation_response(self, mock_get):
        # 0x17B9344 == 24875844
        mock_get.return_value = _resp(_creation_ok(block_number="0x17B9344"))
        assert get_contract_deployment_block("mainnet", ADDR) == 24875844

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_zero_block_falls_through_to_step2(self, mock_get):
        """blockNumber=0 in creation response should not be used; fall through."""
        tx_resp = _tx_ok("0xC350")  # 50000
        mock_get.side_effect = [
            _resp(_creation_ok(block_number="0")),
            _resp(tx_resp),
        ]
        assert get_contract_deployment_block("mainnet", ADDR) == 50000

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_missing_block_falls_through_to_step2(self, mock_get):
        """No blockNumber field → fall through to step 2."""
        tx_resp = _tx_ok("0xC350")
        mock_get.side_effect = [
            _resp(_creation_ok()),   # no blockNumber
            _resp(tx_resp),
        ]
        assert get_contract_deployment_block("mainnet", ADDR) == 50000


# ── Step 2: eth_getTransactionByHash ─────────────────────────────────────────

class TestStep2TxByHash:
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_tx_lookup_succeeds(self, mock_get):
        mock_get.side_effect = [
            _resp(_creation_ok()),      # step 1
            _resp(_tx_ok("0x1E8480")),  # step 2 → 0x1E8480 = 2000000
        ]
        assert get_contract_deployment_block("arbitrum-one", ADDR) == 2000000

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_tx_null_falls_through_to_step3(self, mock_get):
        """eth_getTransactionByHash returns null → fall through to txlistinternal."""
        mock_get.side_effect = [
            _resp(_creation_ok()),          # step 1
            _resp(_tx_null()),              # step 2 → null
            _resp(_txlist_ok("130789")),    # step 3a txlistinternal
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 130789


# ── Step 3: txlistinternal / txlist fallback ──────────────────────────────────

class TestStep3TxListFallback:
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_txlistinternal_used_when_step2_fails(self, mock_get):
        mock_get.side_effect = [
            _resp(_creation_ok()),          # step 1
            _resp(_tx_null()),              # step 2 → null
            _resp(_txlist_ok("999999")),    # step 3a txlistinternal
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 999999

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_txlist_used_when_txlistinternal_empty(self, mock_get):
        mock_get.side_effect = [
            _resp(_creation_ok()),          # step 1
            _resp(_tx_null()),              # step 2 → null
            _resp(_txlist_empty()),         # step 3a txlistinternal → empty
            _resp(_txlist_ok("888888")),    # step 3b txlist
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 888888

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_returns_none_when_all_steps_fail(self, mock_get):
        mock_get.side_effect = [
            _resp(_creation_ok()),   # step 1
            _resp(_tx_null()),       # step 2
            _resp(_txlist_empty()),  # step 3a
            _resp(_txlist_empty()),  # step 3b
        ]
        assert get_contract_deployment_block("optimism", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_optimism_full_path_via_txlistinternal(self, mock_get):
        """Full realistic Optimism path: step1 ok, step2 null, step3 succeeds."""
        mock_get.side_effect = [
            _resp(_creation_ok()),               # getcontractcreation
            _resp(_tx_null()),                   # eth_getTransactionByHash → null
            _resp(_txlist_ok("130789234")),      # txlistinternal → found
        ]
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 130789234
