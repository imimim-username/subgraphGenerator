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
    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
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
