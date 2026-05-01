"""Fetch ABI and contract metadata from Etherscan-compatible explorers."""

import json
import logging
import os
import threading
import time
from typing import Any

import requests

from subgraph_wizard.errors import AbiFetchError
from subgraph_wizard.networks import SUPPORTED_NETWORKS

logger = logging.getLogger(__name__)

# Timeout for API requests in seconds
REQUEST_TIMEOUT = 10

# ── Rate limiter (Etherscan free tier: 5 req/s) ───────────────────────────────
# Enforces a minimum gap between outgoing requests so we stay safely under
# the free-tier limit.  Thread-safe so concurrent server requests don't pile up.
_RATE_LIMIT_INTERVAL = 0.22   # seconds between requests → ≈4.5 req/s
_rate_lock = threading.Lock()
_last_request_at: float = 0.0


def _get(url: str) -> requests.Response:
    """Rate-limited GET wrapper for all Etherscan API calls."""
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        gap = _RATE_LIMIT_INTERVAL - (now - _last_request_at)
        if gap > 0:
            time.sleep(gap)
        _last_request_at = time.monotonic()
    return requests.get(url, timeout=REQUEST_TIMEOUT)

# Mapping of network names to environment variable names for API keys
NETWORK_API_KEY_ENV_VARS = {
    "ethereum": "ETHERSCAN_API_KEY",
    "optimism": "OPTIMISM_ETHERSCAN_API_KEY",
    "arbitrum": "ARBITRUM_ETHERSCAN_API_KEY",
}


def _get_api_key_for_network(network: str) -> str | None:
    """
    Get the API key for a given network from environment variables.
    
    Args:
        network: The network name (e.g., 'ethereum', 'optimism', 'arbitrum')
        
    Returns:
        The API key if found, None otherwise.
    """
    env_var_name = NETWORK_API_KEY_ENV_VARS.get(network)
    if not env_var_name:
        logger.debug("No API key environment variable configured for network: %s", network)
        return None
    
    api_key = os.environ.get(env_var_name)
    if not api_key:
        logger.debug("API key environment variable %s is not set", env_var_name)
        return None
    
    return api_key


def _build_explorer_url(network: str, address: str, api_key: str | None) -> str:
    """
    Build the explorer API URL for fetching an ABI.
    
    Args:
        network: The network name
        address: The contract address
        api_key: Optional API key
        
    Returns:
        The full URL for the API request.
    """
    network_info = SUPPORTED_NETWORKS.get(network)
    if not network_info:
        raise AbiFetchError(f"Unsupported network: {network}")
    
    explorer_host = network_info["explorer"]
    
    url = (
        f"https://{explorer_host}/api"
        f"?module=contract"
        f"&action=getabi"
        f"&address={address}"
    )
    
    if api_key:
        url += f"&apikey={api_key}"
    
    return url


def fetch_abi_from_explorer(network: str, address: str) -> list[dict[str, Any]]:
    """
    Fetch ABI from an Etherscan-compatible explorer API.
    
    Args:
        network: The network name (must be in SUPPORTED_NETWORKS)
        address: The contract address to fetch ABI for
        
    Returns:
        The ABI as a list of dictionaries.
        
    Raises:
        AbiFetchError: If the ABI cannot be fetched. Error messages are sanitized
            to avoid leaking API keys or sensitive URL information.
    """
    # Validate network
    if network not in SUPPORTED_NETWORKS:
        raise AbiFetchError(
            f"Unsupported network: '{network}'. "
            f"Supported networks: {', '.join(SUPPORTED_NETWORKS.keys())}"
        )
    
    # Get API key from environment
    api_key = _get_api_key_for_network(network)
    
    # Build the URL
    url = _build_explorer_url(network, address, api_key)
    
    # Log sanitized information at debug level
    logger.debug(
        "Fetching ABI for address %s on network %s",
        address, network
    )
    
    try:
        response = _get(url)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise AbiFetchError(
            f"Request timed out while fetching ABI from {network} explorer. "
            "Please check your network connection and try again."
        )
    except requests.exceptions.ConnectionError:
        raise AbiFetchError(
            f"Failed to connect to {network} explorer. "
            "Please check your network connection and try again."
        )
    except requests.exceptions.HTTPError as e:
        # Log detailed error at debug level (sanitized)
        logger.debug("HTTP error fetching ABI: status code %s", e.response.status_code)
        raise AbiFetchError(
            f"Failed to fetch ABI from {network} explorer (HTTP error). "
            "The explorer service may be temporarily unavailable. "
            "Please try again later or use a local ABI file."
        )
    except requests.exceptions.RequestException:
        raise AbiFetchError(
            f"Failed to fetch ABI from {network} explorer. "
            "An unexpected network error occurred. "
            "Please try again or use a local ABI file."
        )
    
    # Parse response JSON
    try:
        data = response.json()
    except json.JSONDecodeError:
        logger.debug("Failed to parse explorer response as JSON")
        raise AbiFetchError(
            f"Invalid response from {network} explorer. "
            "The service may be experiencing issues. "
            "Please try again later or use a local ABI file."
        )
    
    # Check for API-level errors
    status = data.get("status")
    message = data.get("message", "")
    result = data.get("result", "")
    
    if status != "1":
        # Determine the type of error and provide user-friendly message
        error_lower = str(result).lower()
        
        if "contract source code not verified" in error_lower:
            raise AbiFetchError(
                f"Contract at {address} is not verified on {network} explorer. "
                "Please verify the contract first, or provide the ABI manually via local file or paste."
            )
        elif "invalid api key" in error_lower or "invalid apikey" in error_lower:
            raise AbiFetchError(
                f"Invalid API key for {network} explorer. "
                "Please check your API key configuration in the .env file."
            )
        elif "rate limit" in error_lower or "max rate limit" in error_lower:
            raise AbiFetchError(
                f"API rate limit exceeded for {network} explorer. "
                "Please wait a moment and try again, or consider using an API key for higher limits."
            )
        elif "invalid address" in error_lower:
            raise AbiFetchError(
                f"Invalid contract address: {address}. "
                "Please check the address format and try again."
            )
        else:
            # Generic error with sanitized message
            logger.debug("Explorer API error: status=%s, message=%s", status, message)
            raise AbiFetchError(
                f"Failed to fetch ABI from {network} explorer. "
                "Contract may not be verified, or API rate limit exceeded. "
                "Please check your API key or try using a local ABI file."
            )
    
    # Parse the ABI from the result
    try:
        abi = json.loads(result)
    except json.JSONDecodeError:
        logger.debug("Failed to parse ABI result as JSON")
        raise AbiFetchError(
            f"Invalid ABI format received from {network} explorer. "
            "The returned data could not be parsed as a valid ABI. "
            "Please try using a local ABI file instead."
        )
    
    # Validate that we got a list
    if not isinstance(abi, list):
        raise AbiFetchError(
            f"Invalid ABI format received from {network} explorer. "
            "Expected a list of ABI entries. "
            "Please try using a local ABI file instead."
        )
    
    logger.info("Successfully fetched ABI for %s on %s (%d entries)", address, network, len(abi))
    
    return abi


def get_supported_networks_for_explorer() -> list[str]:
    """
    Get a list of networks that support explorer ABI fetching.

    Returns:
        List of network names that have explorer API support.
    """
    return [
        network for network in SUPPORTED_NETWORKS
        if network in NETWORK_API_KEY_ENV_VARS
    ]


# ── Deployment block lookup ───────────────────────────────────────────────────

# Networks that are NOT covered by the Etherscan v2 unified API for the
# getcontractcreation endpoint and must use their own chain-specific API.
# Each entry maps a Graph network slug to (api_base_url, env_var_for_key).
_CHAIN_SPECIFIC_APIS: dict[str, tuple[str, str]] = {
    "optimism": ("https://api-optimistic.etherscan.io/api", "OPTIMISM_ETHERSCAN_API_KEY"),
}


def get_contract_deployment_block(network: str, address: str) -> int | None:
    """Return the block number in which a contract was deployed.

    For most chains uses the Etherscan v2 unified API (``ETHERSCAN_API_KEY``).
    Chains listed in ``_CHAIN_SPECIFIC_APIS`` (e.g. Optimism) are NOT covered
    by the v2 unified endpoint and are queried via their own explorer API with
    a dedicated env-var key (e.g. ``OPTIMISM_ETHERSCAN_API_KEY``).

    The lookup sequence:
    1. ``contract/getcontractcreation`` → tx hash + optional blockNumber.
    1b. Use ``blockNumber`` from the creation response if present.
    2. ``proxy/eth_getTransactionByHash`` → blockNumber from the tx.
    3. ``txlistinternal`` / ``txlist`` — reliable L2 fallback.

    Returns ``None`` (rather than raising) when keys are absent, the network
    is unknown, or all lookup steps fail.

    Args:
        network: Graph-cli network name (e.g. ``"mainnet"``, ``"optimism"``).
        address: Contract address (``0x``-prefixed hex string).

    Returns:
        Integer block number, or ``None`` if the block cannot be determined.
    """
    from subgraph_wizard.networks import GRAPH_NETWORK_CHAIN_IDS

    chain_id = GRAPH_NETWORK_CHAIN_IDS.get(network)
    if chain_id is None:
        logger.debug("Network %r not in GRAPH_NETWORK_CHAIN_IDS; skipping lookup", network)
        return None

    # Choose API base URL and key depending on whether the chain needs its own
    # explorer endpoint or can use the unified Etherscan v2 API.
    if network in _CHAIN_SPECIFIC_APIS:
        api_base, key_env = _CHAIN_SPECIFIC_APIS[network]
        api_key = os.environ.get(key_env)
        if not api_key:
            logger.debug(
                "%s not set; skipping deployment block lookup for %s", key_env, network
            )
            return None
        base = f"{api_base}?apikey={api_key}"
    else:
        api_key = os.environ.get("ETHERSCAN_API_KEY")
        if not api_key:
            logger.debug("ETHERSCAN_API_KEY not set; skipping deployment block lookup")
            return None
        base = f"https://api.etherscan.io/v2/api?chainid={chain_id}&apikey={api_key}"

    # ── Step 1: get the creation tx hash ─────────────────────────────────────
    try:
        resp = _get(
            f"{base}&module=contract&action=getcontractcreation"
            f"&contractaddresses={address}",
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(
            "Failed to fetch contract creation info for %s on %s: %s",
            address, network, exc,
        )
        return None

    # Etherscan occasionally returns status "1" with a string result (e.g. rate-limit
    # messages like "Max rate limit reached") instead of the expected list.
    # Guard against that before indexing into the list.
    creation_result = data.get("result")
    if data.get("status") != "1" or not isinstance(creation_result, list) or not creation_result:
        logger.warning(
            "getcontractcreation returned no usable result for %s on %s: %r",
            address, network, creation_result,
        )
        return None

    first = creation_result[0]
    if not isinstance(first, dict):
        logger.warning(
            "Unexpected creation result entry type %r for %s on %s",
            type(first), address, network,
        )
        return None

    tx_hash = first.get("txHash")
    if not tx_hash:
        logger.warning("No txHash in getcontractcreation result for %s on %s", address, network)
        return None

    # ── Step 1b: prefer blockNumber from the creation response directly ───────
    # The Etherscan v2 API returns blockNumber in the getcontractcreation
    # payload.  Using it avoids extra round-trips.  May be decimal or hex.
    block_str = first.get("blockNumber")
    if block_str:
        try:
            block = int(block_str, 16) if str(block_str).startswith("0x") else int(block_str)
            if block > 0:
                logger.info(
                    "Auto-detected startBlock %d for %s on %s (from creation response)",
                    block, address, network,
                )
                return block
        except (ValueError, TypeError):
            logger.debug("Could not parse blockNumber %r from creation result", block_str)

    # ── Step 2: eth_getTransactionByHash (works for most chains) ─────────────
    try:
        resp = _get(
            f"{base}&module=proxy&action=eth_getTransactionByHash"
            f"&txhash={tx_hash}",
        )
        resp.raise_for_status()
        tx_data = resp.json()
        result = tx_data.get("result")
        if isinstance(result, dict):
            block_hex = result.get("blockNumber")
            if block_hex:
                block = int(block_hex, 16)
                logger.info(
                    "Auto-detected startBlock %d for %s on %s (from tx lookup)",
                    block, address, network,
                )
                return block
        logger.warning(
            "eth_getTransactionByHash returned no blockNumber for tx %s on %s: %r",
            tx_hash, network, result,
        )
    except Exception as exc:
        logger.warning("eth_getTransactionByHash failed for tx %s on %s: %s", tx_hash, network, exc)

    # ── Step 3: txlistinternal — reliable fallback for L2 chains (e.g. Optimism)
    # On chains like Optimism, contracts deployed via L1→L2 deposit messages have
    # synthetic tx hashes that the proxy module cannot resolve.  The txlistinternal
    # endpoint queries the chain's own transaction index and reliably returns the
    # creation block as a decimal string.
    for action in ("txlistinternal", "txlist"):
        try:
            resp = _get(
                f"{base}&module=account&action={action}"
                f"&address={address}&startblock=0&endblock=99999999"
                f"&page=1&offset=1&sort=asc",
            )
            resp.raise_for_status()
            list_data = resp.json()
            if list_data.get("status") == "1":
                txs = list_data.get("result", [])
                if txs and isinstance(txs[0], dict):
                    block_str = txs[0].get("blockNumber", "")
                    if block_str:
                        block = int(block_str)  # txlist returns decimal
                        logger.info(
                            "Auto-detected startBlock %d for %s on %s (via %s)",
                            block, address, network, action,
                        )
                        return block
            logger.debug("%s returned no results for %s on %s", action, address, network)
        except Exception as exc:
            logger.warning("%s fallback failed for %s on %s: %s", action, address, network, exc)

    logger.warning(
        "Could not auto-detect startBlock for %s on %s after all methods exhausted",
        address, network,
    )
    return None
