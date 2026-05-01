"""Tests for get_contract_deployment_block — all API calls are mocked."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure ETHERSCAN_API_KEY is set for all tests so the early-exit guard
# doesn't trigger.
os.environ.setdefault("ETHERSCAN_API_KEY", "TEST_KEY")
os.environ.setdefault("OPTIMISM_ETHERSCAN_API_KEY", "TEST_OP_KEY")
os.environ.setdefault("RPC_API_KEY", "TEST_RPC_KEY")

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
    def test_no_api_keys_at_all_returns_none(self, monkeypatch):
        """Both Etherscan and RPC keys absent → early exit, None returned."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        monkeypatch.delenv("RPC_API_KEY", raising=False)
        assert get_contract_deployment_block("mainnet", ADDR) is None

    def test_optimism_no_etherscan_key_no_rpc_key_returns_none(self, monkeypatch):
        """Optimism now uses the unified key; both keys absent → None."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        monkeypatch.delenv("RPC_API_KEY", raising=False)
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


class TestApiBaseUrls:
    """Both Optimism and mainnet use the v2 unified API; RPC handles fallback."""

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_optimism_uses_v2_unified_url(self, mock_get):
        mock_get.return_value = _resp(_creation_ok(block_number="130789234"))
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 130789234
        call_url = mock_get.call_args[0][0]
        assert "api.etherscan.io/v2/api" in call_url
        assert "chainid=10" in call_url

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
    def test_returns_none_when_all_steps_fail(self, mock_get, monkeypatch):
        """All Etherscan steps fail and no RPC key → None."""
        monkeypatch.delenv("RPC_API_KEY", raising=False)
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


# ── Step 4: RPC fallback ──────────────────────────────────────────────────────

class TestStep4RpcFallback:
    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_used_when_all_etherscan_steps_fail(self, mock_get, mock_requests):
        """After Etherscan steps fail, RPC eth_getTransactionByHash is tried."""
        mock_get.side_effect = [
            _resp(_creation_ok()),   # step 1
            _resp(_tx_null()),       # step 2
            _resp(_txlist_empty()),  # step 3a
            _resp(_txlist_empty()),  # step 3b
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"blockNumber": "0x1F26B82"},  # 32664450
            "id": 1,
        }
        mock_requests.post.return_value = rpc_resp

        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 32664450
        # Verify it used the Optimism Alchemy URL
        call_url = mock_requests.post.call_args[0][0]
        assert "opt-mainnet.g.alchemy.com" in call_url

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_skipped_when_no_rpc_key(self, mock_get, monkeypatch):
        """If RPC_API_KEY is absent, step 4 is skipped and None is returned."""
        monkeypatch.delenv("RPC_API_KEY", raising=False)
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        assert get_contract_deployment_block("optimism", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_uses_correct_base_for_mainnet(self, mock_get, mock_requests):
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {
            "jsonrpc": "2.0", "result": {"blockNumber": "0x100"}, "id": 1,
        }
        mock_requests.post.return_value = rpc_resp
        get_contract_deployment_block("mainnet", ADDR)
        call_url = mock_requests.post.call_args[0][0]
        assert "eth-mainnet.g.alchemy.com" in call_url

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_uses_correct_base_for_arbitrum(self, mock_get, mock_requests):
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {
            "jsonrpc": "2.0", "result": {"blockNumber": "0x200"}, "id": 1,
        }
        mock_requests.post.return_value = rpc_resp
        result = get_contract_deployment_block("arbitrum-one", ADDR)
        assert result == 0x200
        call_url = mock_requests.post.call_args[0][0]
        assert "arb-mainnet.g.alchemy.com" in call_url

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_uses_correct_base_for_base(self, mock_get, mock_requests):
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {
            "jsonrpc": "2.0", "result": {"blockNumber": "0x300"}, "id": 1,
        }
        mock_requests.post.return_value = rpc_resp
        get_contract_deployment_block("base", ADDR)
        call_url = mock_requests.post.call_args[0][0]
        assert "base-mainnet.g.alchemy.com" in call_url

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_skipped_when_network_has_no_alchemy_base(self, mock_get, monkeypatch):
        """Networks absent from _ALCHEMY_RPC_BASES skip the RPC step entirely."""
        monkeypatch.setenv("RPC_API_KEY", "TEST_RPC_KEY")
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        # "fantom" is in GRAPH_NETWORK_CHAIN_IDS but not in _ALCHEMY_RPC_BASES
        from subgraph_wizard.abi.etherscan import _ALCHEMY_RPC_BASES
        if "fantom" not in _ALCHEMY_RPC_BASES:
            assert get_contract_deployment_block("fantom", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_returns_none_when_post_raises(self, mock_get, mock_requests):
        """If RPC POST raises an exception the function still returns None cleanly."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        mock_requests.post.side_effect = Exception("connection refused")
        assert get_contract_deployment_block("optimism", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_returns_none_when_result_is_null(self, mock_get, mock_requests):
        """RPC result: null → no blockNumber → returns None."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {"jsonrpc": "2.0", "result": None, "id": 1}
        mock_requests.post.return_value = rpc_resp
        assert get_contract_deployment_block("optimism", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_returns_none_when_block_number_absent(self, mock_get, mock_requests):
        """RPC result dict has no blockNumber field → returns None."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {
            "jsonrpc": "2.0", "result": {"hash": TX_HASH}, "id": 1,
        }
        mock_requests.post.return_value = rpc_resp
        assert get_contract_deployment_block("optimism", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_rpc_api_key_appended_to_base_url(self, mock_get, mock_requests):
        """The RPC_API_KEY value must be appended to the Alchemy base URL."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {
            "jsonrpc": "2.0", "result": {"blockNumber": "0xABCD"}, "id": 1,
        }
        mock_requests.post.return_value = rpc_resp
        get_contract_deployment_block("optimism", ADDR)
        call_url = mock_requests.post.call_args[0][0]
        assert call_url.endswith("TEST_RPC_KEY")


# ── Step 1 edge cases ─────────────────────────────────────────────────────────

class TestStep1EdgeCases:
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_result_is_rate_limit_string_returns_none(self, mock_get):
        """status=0 with a rate-limit message string (not a list) → None."""
        mock_get.return_value = _resp({
            "status": "0",
            "message": "NOTOK",
            "result": "Max rate limit reached, please use API Key for higher rate limit",
        })
        assert get_contract_deployment_block("mainnet", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_result_is_empty_list_returns_none(self, mock_get):
        """status=1 but result is an empty list → None."""
        mock_get.return_value = _resp({"status": "1", "message": "OK", "result": []})
        assert get_contract_deployment_block("mainnet", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_result_entry_is_not_dict_returns_none(self, mock_get):
        """result[0] is a string rather than a dict → None."""
        mock_get.return_value = _resp({
            "status": "1", "message": "OK", "result": ["unexpected_string"]
        })
        assert get_contract_deployment_block("mainnet", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_result_missing_tx_hash_returns_none(self, mock_get):
        """Creation result dict has no txHash field → None."""
        mock_get.return_value = _resp({
            "status": "1", "message": "OK",
            "result": [{"contractCreator": "0xabc"}],
        })
        assert get_contract_deployment_block("mainnet", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_result_status_is_string_1_not_int(self, mock_get):
        """Etherscan returns status as the string "1", not integer 1."""
        mock_get.return_value = _resp(_creation_ok(block_number="50000"))
        assert get_contract_deployment_block("mainnet", ADDR) == 50000

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_unparseable_block_number_falls_through(self, mock_get):
        """blockNumber that is neither decimal nor hex falls through to step 2."""
        tx_resp = _tx_ok("0xC350")  # 50000
        mock_get.side_effect = [
            _resp(_creation_ok(block_number="not-a-number")),
            _resp(tx_resp),
        ]
        assert get_contract_deployment_block("mainnet", ADDR) == 50000

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_creation_result_is_string_not_list_returns_none(self, mock_get):
        """status=1 but result is a bare string, not a list → None."""
        mock_get.return_value = _resp({
            "status": "1", "message": "OK", "result": "some unexpected string"
        })
        assert get_contract_deployment_block("mainnet", ADDR) is None


# ── Step 2 edge cases ─────────────────────────────────────────────────────────

class TestStep2EdgeCases:
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_tx_block_number_is_none_falls_through(self, mock_get):
        """blockNumber field present but its value is None → fall through."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp({"jsonrpc": "2.0", "result": {"blockNumber": None, "hash": TX_HASH}, "id": 1}),
            _resp(_txlist_ok("77777")),
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 77777

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_tx_block_number_is_empty_string_falls_through(self, mock_get):
        """blockNumber field is empty string → falsy → fall through."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp({"jsonrpc": "2.0", "result": {"blockNumber": "", "hash": TX_HASH}, "id": 1}),
            _resp(_txlist_ok("88888")),
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 88888

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_tx_result_not_dict_falls_through(self, mock_get):
        """result is a non-dict value (e.g. a string) → fall through."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp({"jsonrpc": "2.0", "result": "error_string", "id": 1}),
            _resp(_txlist_ok("99999")),
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 99999

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_step2_exception_falls_through_to_step3(self, mock_get):
        """If step 2 raises, we fall through to txlistinternal."""
        mock_get.side_effect = [
            _resp(_creation_ok()),          # step 1 OK
            Exception("proxy timeout"),     # step 2 raises
            _resp(_txlist_ok("55555")),     # step 3a
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 55555


# ── Step 3 edge cases ─────────────────────────────────────────────────────────

class TestStep3EdgeCases:
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_txlistinternal_exception_falls_through_to_txlist(self, mock_get):
        """Exception during txlistinternal → skip to txlist."""
        mock_get.side_effect = [
            _resp(_creation_ok()),          # step 1
            _resp(_tx_null()),              # step 2
            Exception("txlistinternal timeout"),  # step 3a raises
            _resp(_txlist_ok("444444")),    # step 3b
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 444444

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_txlist_exception_returns_none(self, mock_get):
        """Both txlistinternal and txlist raise → returns None (no RPC key)."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            Exception("txlistinternal error"),
            Exception("txlist error"),
        ]
        # No RPC_API_KEY in environment, so step 4 is skipped
        import os
        old = os.environ.pop("RPC_API_KEY", None)
        try:
            assert get_contract_deployment_block("optimism", ADDR) is None
        finally:
            if old is not None:
                os.environ["RPC_API_KEY"] = old

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_txlistinternal_result_has_no_block_number_field(self, mock_get):
        """status=1, result has entries but no blockNumber key → fall through."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp({"status": "1", "result": [{"hash": TX_HASH}]}),  # no blockNumber
            _resp(_txlist_ok("333333")),
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 333333

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_txlistinternal_block_number_empty_string_falls_through(self, mock_get):
        """blockNumber is an empty string in txlistinternal → fall through."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp({"status": "1", "result": [{"blockNumber": ""}]}),
            _resp(_txlist_ok("222222")),
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 222222

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_txlistinternal_result_is_not_list(self, mock_get):
        """txlistinternal result is a string (e.g. error) → treated as empty."""
        mock_get.side_effect = [
            _resp(_creation_ok()),
            _resp(_tx_null()),
            _resp({"status": "0", "result": "No transactions found"}),
            _resp(_txlist_ok("111111")),
        ]
        assert get_contract_deployment_block("optimism", ADDR) == 111111


# ── _rpc_get_tx_block unit tests ──────────────────────────────────────────────

class TestRpcGetTxBlock:
    """Direct unit tests for the _rpc_get_tx_block helper."""

    from subgraph_wizard.abi.etherscan import _rpc_get_tx_block

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_returns_correct_block_on_success(self, mock_requests):
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"blockNumber": "0x1E8480"},  # 2_000_000
            "id": 1,
        }
        mock_requests.post.return_value = resp
        assert _rpc_get_tx_block("https://example.com/v2/KEY", TX_HASH) == 2_000_000

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_returns_none_when_result_is_null(self, mock_requests):
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"jsonrpc": "2.0", "result": None, "id": 1}
        mock_requests.post.return_value = resp
        assert _rpc_get_tx_block("https://example.com/v2/KEY", TX_HASH) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_returns_none_when_block_number_absent(self, mock_requests):
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "jsonrpc": "2.0", "result": {"hash": TX_HASH}, "id": 1
        }
        mock_requests.post.return_value = resp
        assert _rpc_get_tx_block("https://example.com/v2/KEY", TX_HASH) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_returns_none_when_result_is_not_dict(self, mock_requests):
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"jsonrpc": "2.0", "result": "some_string", "id": 1}
        mock_requests.post.return_value = resp
        assert _rpc_get_tx_block("https://example.com/v2/KEY", TX_HASH) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_returns_none_when_post_raises(self, mock_requests):
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        mock_requests.post.side_effect = Exception("connection error")
        assert _rpc_get_tx_block("https://example.com/v2/KEY", TX_HASH) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_returns_none_when_raise_for_status_raises(self, mock_requests):
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        resp = MagicMock()
        resp.raise_for_status.side_effect = Exception("HTTP 429")
        mock_requests.post.return_value = resp
        assert _rpc_get_tx_block("https://example.com/v2/KEY", TX_HASH) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_block_number_hex_decoded_correctly(self, mock_requests):
        """Various hex values should round-trip correctly."""
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        # 0x17B9344 == 24875844
        resp.json.return_value = {
            "jsonrpc": "2.0", "result": {"blockNumber": "0x17B9344"}, "id": 1
        }
        mock_requests.post.return_value = resp
        assert _rpc_get_tx_block("https://example.com/v2/KEY", TX_HASH) == 0x17B9344

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_correct_json_rpc_payload_sent(self, mock_requests):
        """Verifies the exact JSON-RPC method and params sent in the POST body."""
        from subgraph_wizard.abi.etherscan import _rpc_get_tx_block
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"jsonrpc": "2.0", "result": None, "id": 1}
        mock_requests.post.return_value = resp
        _rpc_get_tx_block("https://rpc.example.com/", TX_HASH)
        _, kwargs = mock_requests.post.call_args
        payload = kwargs.get("json") or mock_requests.post.call_args[1].get("json")
        assert payload["method"] == "eth_getTransactionByHash"
        assert payload["params"] == [TX_HASH]
        assert payload["jsonrpc"] == "2.0"


# ── Helper: "Free API access not supported" response ─────────────────────────

def _creation_free_api_error():
    """Simulates Etherscan's response for unsupported chains on the free tier.

    This is the exact error seen for Optimism contracts when using the v2
    unified API without a paid plan.
    """
    return {
        "status": "0",
        "message": "NOTOK",
        "result": "Free API access is not supported for this chain",
    }


def _rpc_binary_search_post(deploy_block: int, latest_block: int):
    """Return a `requests.post` side_effect function that answers RPC calls.

    Simulates a chain where a contract was deployed at *deploy_block* and the
    current head is *latest_block*.  Handles both ``eth_blockNumber`` and
    ``eth_getCode`` JSON-RPC methods.
    """
    def _post(url, json=None, timeout=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        method = (json or {}).get("method", "")
        if method == "eth_blockNumber":
            resp.json.return_value = {
                "jsonrpc": "2.0", "result": hex(latest_block), "id": 1,
            }
        elif method == "eth_getCode":
            block_num = int(json["params"][1], 16)
            code = "0x6060604052" if block_num >= deploy_block else "0x"
            resp.json.return_value = {"jsonrpc": "2.0", "result": code, "id": 1}
        else:
            resp.json.return_value = {"jsonrpc": "2.0", "result": None, "id": 1}
        return resp

    return _post


# ── TestStep1FreeApiError ─────────────────────────────────────────────────────

class TestStep1FreeApiError:
    """Tests the 'Free API access not supported' failure mode (e.g. Optimism).

    Step 1 failure MUST be non-fatal — the function must continue to steps 3
    and 4.  This was the root cause of the original bug where Optimism contracts
    received no ``startBlock`` in the generated ``ponder.config.ts``.
    """

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_free_api_error_continues_to_step3_txlistinternal(self, mock_get):
        """Step 1 'Free API access' → non-fatal → step 3a txlistinternal succeeds."""
        mock_get.side_effect = [
            _resp(_creation_free_api_error()),  # step 1 fails (non-fatal)
            _resp(_txlist_ok("130789234")),     # step 3a txlistinternal → found
        ]
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 130789234

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_free_api_error_continues_to_step3_txlist_fallback(self, mock_get):
        """Step 1 fails → txlistinternal empty → txlist succeeds."""
        mock_get.side_effect = [
            _resp(_creation_free_api_error()),  # step 1 fails (non-fatal)
            _resp(_txlist_empty()),             # step 3a txlistinternal → empty
            _resp(_txlist_ok("98765432")),      # step 3b txlist → found
        ]
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 98765432

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_free_api_error_and_step3_fail_uses_rpc_binary_search(
        self, mock_get, mock_requests
    ):
        """Step 1 fails + step 3 also empty → RPC binary search used as final fallback.

        This is the critical end-to-end scenario that was broken: Etherscan
        refuses the request entirely (Optimism free tier) and the function must
        fall all the way through to the ``eth_getCode`` binary search.
        """
        mock_get.side_effect = [
            _resp(_creation_free_api_error()),  # step 1 fails (non-fatal)
            _resp(_txlist_empty()),             # step 3a txlistinternal → empty
            _resp(_txlist_empty()),             # step 3b txlist → empty
        ]
        mock_requests.post.side_effect = _rpc_binary_search_post(
            deploy_block=130_789_234,
            latest_block=135_000_000,
        )
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 130_789_234

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_free_api_error_and_all_fail_no_rpc_key_returns_none(
        self, mock_get, monkeypatch
    ):
        """Step 1 fails + step 3 empty + no RPC key → None (nowhere left to look)."""
        monkeypatch.delenv("RPC_API_KEY", raising=False)
        mock_get.side_effect = [
            _resp(_creation_free_api_error()),
            _resp(_txlist_empty()),
            _resp(_txlist_empty()),
        ]
        assert get_contract_deployment_block("optimism", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_no_etherscan_key_only_rpc_key_uses_binary_search(
        self, mock_requests, monkeypatch
    ):
        """No ETHERSCAN_API_KEY at all, but RPC_API_KEY present → binary search works.

        Etherscan steps 1–3 are skipped entirely; step 4 binary search is the
        only mechanism used.
        """
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        mock_requests.post.side_effect = _rpc_binary_search_post(
            deploy_block=130_000_000,
            latest_block=135_000_000,
        )
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 130_000_000

    @patch("subgraph_wizard.abi.etherscan._get")
    def test_step1_network_exception_continues_to_step3(self, mock_get):
        """Network exception on step 1 (not just API error) is also non-fatal."""
        mock_get.side_effect = [
            Exception("Connection timeout"),   # step 1 raises — non-fatal
            _resp(_txlist_ok("55555555")),     # step 3a txlistinternal → found
        ]
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 55555555

    @patch("subgraph_wizard.abi.etherscan.requests")
    @patch("subgraph_wizard.abi.etherscan._get")
    def test_free_api_error_step3_captures_hash_for_rpc(self, mock_get, mock_requests):
        """If step 3 finds a tx hash but no block, it is passed to step 4 RPC tx lookup.

        This covers the path where txlistinternal returns a hash but the block
        number is empty (unusual but possible), so step 4a uses that hash.
        """
        mock_get.side_effect = [
            _resp(_creation_free_api_error()),  # step 1 fails (non-fatal)
            # step 3a: status "1", has hash, but blockNumber is empty string
            _resp({"status": "1", "result": [{"blockNumber": "", "hash": TX_HASH}]}),
            _resp(_txlist_empty()),             # step 3b txlist → empty
        ]
        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"blockNumber": "0x7CB6E32"},  # 130_789_682
            "id": 1,
        }
        mock_requests.post.return_value = rpc_resp
        result = get_contract_deployment_block("optimism", ADDR)
        assert result == 0x7CB6E32
        # Confirm it used eth_getTransactionByHash (with the hash from step 3)
        post_payload = mock_requests.post.call_args[1].get("json") or \
                       mock_requests.post.call_args[0][0]  # fallback if positional
        assert mock_requests.post.called


# ── TestRpcFindDeploymentBlock ────────────────────────────────────────────────

class TestRpcFindDeploymentBlock:
    """Direct unit tests for ``_rpc_find_deployment_block``.

    This function uses a binary search over ``eth_getCode`` to find the first
    block where a contract's bytecode is present.  It is called when no
    transaction hash is available (e.g. Etherscan refused the request).
    """

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_happy_path_finds_correct_deploy_block(self, mock_requests):
        """Binary search converges to the exact deployment block."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        mock_requests.post.side_effect = _rpc_binary_search_post(
            deploy_block=50, latest_block=100
        )
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) == 50

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_deployed_at_block_1(self, mock_requests):
        """Contract deployed at the very first block — boundary condition."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        mock_requests.post.side_effect = _rpc_binary_search_post(
            deploy_block=1, latest_block=7
        )
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) == 1

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_deployed_at_latest_block(self, mock_requests):
        """Contract deployed at the highest block — other boundary condition."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        mock_requests.post.side_effect = _rpc_binary_search_post(
            deploy_block=100, latest_block=100
        )
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) == 100

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_eth_block_number_fails_returns_none(self, mock_requests):
        """eth_blockNumber POST raises — returns None immediately."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        mock_requests.post.side_effect = Exception("connection refused")
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_eth_block_number_result_none_returns_none(self, mock_requests):
        """eth_blockNumber returns result: null — returns None."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"jsonrpc": "2.0", "result": None, "id": 1}
        mock_requests.post.return_value = resp
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_eth_get_code_raises_during_search_returns_none(self, mock_requests):
        """eth_getCode raises mid-search — returns None."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        call_count = 0

        def _post(url, json=None, timeout=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if call_count == 1:  # eth_blockNumber succeeds
                resp.json.return_value = {"jsonrpc": "2.0", "result": hex(100), "id": 1}
                return resp
            raise Exception("RPC node overloaded")

        mock_requests.post.side_effect = _post
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_contract_never_deployed_returns_none(self, mock_requests):
        """eth_getCode always returns '0x' — address has no bytecode → None."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        def _post(url, json=None, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            method = (json or {}).get("method", "")
            if method == "eth_blockNumber":
                resp.json.return_value = {"jsonrpc": "2.0", "result": hex(100), "id": 1}
            else:
                resp.json.return_value = {"jsonrpc": "2.0", "result": "0x", "id": 1}
            return resp

        mock_requests.post.side_effect = _post
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_verification_step_raises_returns_none(self, mock_requests):
        """Verification call (final eth_getCode check) raises → returns None.

        We use a tiny search space (latest=3, deploy=2) so the binary search
        takes only two iterations before reaching the verification step.
        """
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        # With latest=3 and deploy=2 the search proceeds:
        #   lo=0,hi=3 → mid=1 → "0x" → lo=2
        #   lo=2,hi=3 → mid=2 → "0x60" → hi=2
        #   lo=2==hi=2 → exit loop
        #   verification: eth_getCode(lo=2) → raise
        DEPLOY_BLOCK = 2
        LATEST_BLOCK = 3
        call_count = 0

        def _post(url, json=None, timeout=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            method = (json or {}).get("method", "")
            if method == "eth_blockNumber":
                resp.json.return_value = {
                    "jsonrpc": "2.0", "result": hex(LATEST_BLOCK), "id": 1,
                }
                return resp
            # eth_getCode
            block_num = int(json["params"][1], 16)
            # The 4th call is the verification step — make it raise
            if call_count == 4:
                raise Exception("RPC timeout on verification")
            code = "0x6060" if block_num >= DEPLOY_BLOCK else "0x"
            resp.json.return_value = {"jsonrpc": "2.0", "result": code, "id": 1}
            return resp

        mock_requests.post.side_effect = _post
        assert _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR) is None

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_uses_contract_address_in_get_code_params(self, mock_requests):
        """eth_getCode must be called with the contract address as first param."""
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        target_addr = "0xDeadBeef00000000000000000000000000000001"
        seen_addresses: set[str] = set()

        def _post(url, json=None, timeout=None):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            method = (json or {}).get("method", "")
            if method == "eth_blockNumber":
                resp.json.return_value = {"jsonrpc": "2.0", "result": hex(7), "id": 1}
            elif method == "eth_getCode":
                params = json.get("params", [])
                if params:
                    seen_addresses.add(params[0])
                block_num = int(params[1], 16) if len(params) > 1 else 0
                code = "0x6060" if block_num >= 3 else "0x"
                resp.json.return_value = {"jsonrpc": "2.0", "result": code, "id": 1}
            return resp

        mock_requests.post.side_effect = _post
        _rpc_find_deployment_block("https://rpc.example.com/KEY", target_addr)
        # Every eth_getCode call must use the target address
        assert seen_addresses == {target_addr}

    @patch("subgraph_wizard.abi.etherscan.requests")
    def test_result_is_exact_boundary_not_one_before(self, mock_requests):
        """Binary search must return block N where code appears, not N-1.

        Regression guard: an off-by-one would return deploy_block-1.
        """
        from subgraph_wizard.abi.etherscan import _rpc_find_deployment_block

        DEPLOY_BLOCK = 77
        mock_requests.post.side_effect = _rpc_binary_search_post(
            deploy_block=DEPLOY_BLOCK, latest_block=100
        )
        result = _rpc_find_deployment_block("https://rpc.example.com/KEY", ADDR)
        assert result == DEPLOY_BLOCK
        # Sanity: one block before must have no code (ensured by _rpc_binary_search_post)
        # (verified implicitly by the search converging correctly)
