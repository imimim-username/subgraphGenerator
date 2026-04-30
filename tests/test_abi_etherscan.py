"""Tests for Etherscan ABI fetching functionality."""

import json
import pytest
from unittest.mock import patch, MagicMock

from subgraph_wizard.abi.etherscan import (
    fetch_abi_from_explorer,
    get_supported_networks_for_explorer,
    _get_api_key_for_network,
    _build_explorer_url,
    REQUEST_TIMEOUT,
)
from subgraph_wizard.errors import AbiFetchError


# Sample valid ABI for testing
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
        "name": "balanceOf",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
]

SAMPLE_ADDRESS = "0x1234567890abcdef1234567890abcdef12345678"


class TestGetApiKeyForNetwork:
    """Tests for _get_api_key_for_network helper."""

    def test_get_ethereum_api_key(self, monkeypatch):
        """Should return API key for ethereum when env var is set."""
        monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key-123")
        assert _get_api_key_for_network("ethereum") == "test-key-123"

    def test_get_optimism_api_key(self, monkeypatch):
        """Should return API key for optimism when env var is set."""
        monkeypatch.setenv("OPTIMISM_ETHERSCAN_API_KEY", "optimism-key-456")
        assert _get_api_key_for_network("optimism") == "optimism-key-456"

    def test_get_arbitrum_api_key(self, monkeypatch):
        """Should return API key for arbitrum when env var is set."""
        monkeypatch.setenv("ARBITRUM_ETHERSCAN_API_KEY", "arb-key-789")
        assert _get_api_key_for_network("arbitrum") == "arb-key-789"

    def test_returns_none_when_env_var_not_set(self, monkeypatch):
        """Should return None when API key env var is not set."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        assert _get_api_key_for_network("ethereum") is None

    def test_returns_none_for_unknown_network(self):
        """Should return None for networks without configured API key env vars."""
        assert _get_api_key_for_network("unknown-network") is None


class TestBuildExplorerUrl:
    """Tests for _build_explorer_url helper."""

    def test_build_url_for_ethereum_without_api_key(self):
        """Should build correct URL for ethereum without API key."""
        url = _build_explorer_url("ethereum", SAMPLE_ADDRESS, None)
        assert "api.etherscan.io" in url
        assert f"address={SAMPLE_ADDRESS}" in url
        assert "apikey" not in url

    def test_build_url_for_ethereum_with_api_key(self):
        """Should build correct URL for ethereum with API key."""
        url = _build_explorer_url("ethereum", SAMPLE_ADDRESS, "test-key")
        assert "api.etherscan.io" in url
        assert f"address={SAMPLE_ADDRESS}" in url
        assert "apikey=test-key" in url

    def test_build_url_for_optimism(self):
        """Should build correct URL for optimism."""
        url = _build_explorer_url("optimism", SAMPLE_ADDRESS, None)
        assert "api-optimistic.etherscan.io" in url

    def test_build_url_for_arbitrum(self):
        """Should build correct URL for arbitrum."""
        url = _build_explorer_url("arbitrum", SAMPLE_ADDRESS, None)
        assert "api.arbiscan.io" in url

    def test_raises_error_for_unsupported_network(self):
        """Should raise AbiFetchError for unsupported network."""
        with pytest.raises(AbiFetchError) as excinfo:
            _build_explorer_url("unsupported-network", SAMPLE_ADDRESS, None)
        assert "Unsupported network" in str(excinfo.value)


class TestFetchAbiFromExplorer:
    """Tests for fetch_abi_from_explorer function."""

    def test_successful_fetch(self, monkeypatch):
        """Should successfully fetch and parse ABI from explorer."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": json.dumps(SAMPLE_ABI),
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response) as mock_get:
            abi = fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            assert abi == SAMPLE_ABI
            mock_get.assert_called_once()
            # Verify timeout is set
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["timeout"] == REQUEST_TIMEOUT

    def test_successful_fetch_with_api_key(self, monkeypatch):
        """Should include API key in request when available."""
        monkeypatch.setenv("ETHERSCAN_API_KEY", "my-api-key")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": json.dumps(SAMPLE_ABI),
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response) as mock_get:
            fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            # Verify API key is included in URL
            call_url = mock_get.call_args[0][0]
            assert "apikey=my-api-key" in call_url

    def test_raises_error_for_unsupported_network(self):
        """Should raise AbiFetchError for unsupported network."""
        with pytest.raises(AbiFetchError) as excinfo:
            fetch_abi_from_explorer("unsupported-network", SAMPLE_ADDRESS)
        
        assert "Unsupported network" in str(excinfo.value)
        assert "unsupported-network" in str(excinfo.value)

    def test_handles_timeout_error(self, monkeypatch):
        """Should raise AbiFetchError with friendly message on timeout."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        import requests
        with patch("subgraph_wizard.abi.etherscan.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()
            
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "timed out" in error_msg.lower()
            assert "ETHERSCAN_API_KEY" not in error_msg  # No API key leak

    def test_handles_connection_error(self, monkeypatch):
        """Should raise AbiFetchError with friendly message on connection error."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        import requests
        with patch("subgraph_wizard.abi.etherscan.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "connect" in error_msg.lower()

    def test_handles_http_error(self, monkeypatch):
        """Should raise AbiFetchError with friendly message on HTTP error."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch("subgraph_wizard.abi.etherscan.requests.get") as mock_get:
            http_error = requests.exceptions.HTTPError(response=mock_response)
            mock_get.return_value.raise_for_status.side_effect = http_error
            
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "HTTP error" in error_msg

    def test_handles_unverified_contract(self, monkeypatch):
        """Should raise AbiFetchError with clear message for unverified contract."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "0",
            "message": "NOTOK",
            "result": "Contract source code not verified",
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "not verified" in error_msg.lower()
            assert SAMPLE_ADDRESS in error_msg

    def test_handles_invalid_api_key(self, monkeypatch):
        """Should raise AbiFetchError with clear message for invalid API key."""
        monkeypatch.setenv("ETHERSCAN_API_KEY", "invalid-key")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "0",
            "message": "NOTOK",
            "result": "Invalid API Key",
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "invalid api key" in error_msg.lower()
            # Should NOT contain the actual API key
            assert "invalid-key" not in error_msg

    def test_handles_rate_limit(self, monkeypatch):
        """Should raise AbiFetchError with clear message on rate limit."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "0",
            "message": "NOTOK",
            "result": "Max rate limit reached",
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "rate limit" in error_msg.lower()

    def test_handles_invalid_address(self, monkeypatch):
        """Should raise AbiFetchError with clear message for invalid address."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "0",
            "message": "NOTOK",
            "result": "Invalid address format",
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", "invalid-address")
            
            error_msg = str(excinfo.value)
            assert "invalid" in error_msg.lower()
            assert "address" in error_msg.lower()

    def test_handles_invalid_json_response(self, monkeypatch):
        """Should raise AbiFetchError when response is not valid JSON."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("test", "test", 0)
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "invalid response" in error_msg.lower()

    def test_handles_invalid_abi_json_in_result(self, monkeypatch):
        """Should raise AbiFetchError when ABI result is not valid JSON."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": "not valid json [[[",
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "invalid abi format" in error_msg.lower()

    def test_handles_non_list_abi_result(self, monkeypatch):
        """Should raise AbiFetchError when ABI result is not a list."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": json.dumps({"not": "a list"}),
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "expected a list" in error_msg.lower()

    def test_handles_generic_api_error(self, monkeypatch):
        """Should raise AbiFetchError with sanitized message for unknown API errors."""
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "0",
            "message": "NOTOK",
            "result": "Some unknown error occurred with sensitive info",
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch("subgraph_wizard.abi.etherscan.requests.get", return_value=mock_response):
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            # Should not expose the raw error message
            assert "sensitive info" not in error_msg
            # Should provide user-friendly guidance
            assert "local abi file" in error_msg.lower()


class TestGetSupportedNetworksForExplorer:
    """Tests for get_supported_networks_for_explorer function."""

    def test_returns_list_of_supported_networks(self):
        """Should return list of networks with explorer support."""
        networks = get_supported_networks_for_explorer()
        
        assert isinstance(networks, list)
        assert "ethereum" in networks
        assert "optimism" in networks
        assert "arbitrum" in networks

    def test_returned_networks_are_in_supported_networks(self):
        """All returned networks should be in SUPPORTED_NETWORKS."""
        from subgraph_wizard.networks import SUPPORTED_NETWORKS
        
        networks = get_supported_networks_for_explorer()
        
        for network in networks:
            assert network in SUPPORTED_NETWORKS


class TestErrorMessageSanitization:
    """Tests to verify error messages don't leak sensitive information."""

    def test_api_key_not_in_timeout_error(self, monkeypatch):
        """API key should not appear in timeout error messages."""
        monkeypatch.setenv("ETHERSCAN_API_KEY", "super-secret-key-12345")
        
        import requests
        with patch("subgraph_wizard.abi.etherscan.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()
            
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "super-secret-key-12345" not in error_msg
            assert "ETHERSCAN_API_KEY" not in error_msg

    def test_url_not_in_connection_error(self, monkeypatch):
        """Full URL with query params should not appear in connection error messages."""
        monkeypatch.setenv("ETHERSCAN_API_KEY", "my-api-key")
        
        import requests
        with patch("subgraph_wizard.abi.etherscan.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            with pytest.raises(AbiFetchError) as excinfo:
                fetch_abi_from_explorer("ethereum", SAMPLE_ADDRESS)
            
            error_msg = str(excinfo.value)
            assert "apikey=" not in error_msg
            assert "my-api-key" not in error_msg

