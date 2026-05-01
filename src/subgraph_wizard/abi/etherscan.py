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
# Optimism is intentionally NOT listed here — the unified key is tried first
# and the RPC fallback (step 4) handles it when Etherscan fails.
_CHAIN_SPECIFIC_APIS: dict[str, tuple[str, str]] = {}

# Alchemy RPC base URLs per Graph network slug.
# The full endpoint is  {base}{RPC_API_KEY}.
# Used as a final fallback when all Etherscan lookups fail.
_ALCHEMY_RPC_BASES: dict[str, str] = {
    "mainnet":       "https://eth-mainnet.g.alchemy.com/v2/",
    "optimism":      "https://opt-mainnet.g.alchemy.com/v2/",
    "arbitrum-one":  "https://arb-mainnet.g.alchemy.com/v2/",
    "base":          "https://base-mainnet.g.alchemy.com/v2/",
    "polygon":       "https://polygon-mainnet.g.alchemy.com/v2/",
    "bnb":           "https://bnb-mainnet.g.alchemy.com/v2/",
    "avalanche":     "https://avax-mainnet.g.alchemy.com/v2/",
    "gnosis":        "https://gnosis-mainnet.g.alchemy.com/v2/",
    "zksync-era":    "https://zksync-mainnet.g.alchemy.com/v2/",
    "linea":         "https://linea-mainnet.g.alchemy.com/v2/",
    "scroll":        "https://scroll-mainnet.g.alchemy.com/v2/",
    "sepolia":       "https://eth-sepolia.g.alchemy.com/v2/",
}


def _rpc_get_tx_block(rpc_url: str, tx_hash: str) -> int | None:
    """Call ``eth_getTransactionByHash`` on a JSON-RPC endpoint.

    Uses a direct POST (bypassing the Etherscan rate limiter) since this
    targets a different service.  Returns the block number as an integer,
    or ``None`` on any failure.
    """
    try:
        r = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "method": "eth_getTransactionByHash",
                  "params": [tx_hash], "id": 1},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        result = r.json().get("result") or {}
        block_hex = result.get("blockNumber") if isinstance(result, dict) else None
        if block_hex:
            return int(block_hex, 16)
    except Exception as exc:
        logger.debug("RPC eth_getTransactionByHash failed for %s: %s", tx_hash, exc)
    return None


def _rpc_find_deployment_block(rpc_url: str, address: str) -> int | None:
    """Find the deployment block via ``eth_getCode`` binary search.

    Used when no transaction hash is available (e.g. Etherscan refused the
    request entirely).  Makes O(log(latest_block)) RPC calls — typically
    ~27 calls for mainnet, ~30 for Optimism.  Each call is a fast JSON-RPC
    POST so the total latency is usually under 5 seconds.

    Args:
        rpc_url: Full Alchemy (or compatible) JSON-RPC endpoint URL.
        address: Contract address to locate.

    Returns:
        The first block number where ``eth_getCode`` returns non-empty
        bytecode, or ``None`` on any failure.
    """
    # ── Get latest block number to establish the search ceiling ──────────────
    try:
        r = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        hi_hex = r.json().get("result")
        if not hi_hex:
            return None
        hi = int(hi_hex, 16)
    except Exception as exc:
        logger.debug("eth_blockNumber failed during binary search for %s: %s", address, exc)
        return None

    # ── Binary search ─────────────────────────────────────────────────────────
    lo = 0
    while lo < hi:
        mid = (lo + hi) // 2
        try:
            r = requests.post(
                rpc_url,
                json={"jsonrpc": "2.0", "method": "eth_getCode",
                      "params": [address, hex(mid)], "id": 1},
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            code = r.json().get("result", "0x") or "0x"
        except Exception as exc:
            logger.debug("eth_getCode at block %d failed during binary search: %s", mid, exc)
            return None
        if code != "0x":
            hi = mid
        else:
            lo = mid + 1

    # ── Verify the candidate block ────────────────────────────────────────────
    try:
        r = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "method": "eth_getCode",
                  "params": [address, hex(lo)], "id": 1},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        code = r.json().get("result", "0x") or "0x"
        if code != "0x":
            return lo
    except Exception as exc:
        logger.debug("eth_getCode verification at block %d failed: %s", lo, exc)
    return None


def get_contract_deployment_block(network: str, address: str) -> int | None:
    """Return the block number in which a contract was deployed.

    Uses a four-step fallback chain so that temporary or permanent failures
    at any individual step still give later steps a chance to succeed.

    Steps:
    1.  ``getcontractcreation`` (Etherscan v2 unified API) → tx hash + optional
        ``blockNumber``.  A non-"1" status (e.g. "Free API access not supported
        for this chain") is logged as a warning but does **not** abort — the
        function continues to steps 3 and 4.
    1b. If the creation response includes a valid ``blockNumber``, return it
        immediately (saves two extra round-trips).
    2.  ``proxy/eth_getTransactionByHash`` — only attempted when a tx hash is
        available from step 1.
    3.  ``txlistinternal`` then ``txlist`` — need only the contract address, so
        they work even when step 1 fails entirely.  A tx hash found here is
        saved for use by step 4 if needed.
    4.  RPC fallback via Alchemy (``RPC_API_KEY``):
        a. ``eth_getTransactionByHash`` if a tx hash was obtained in steps 1–3.
        b. ``eth_getCode`` binary search — works with no tx hash at all.

    Returns ``None`` (rather than raising) when all API keys are absent, the
    network is unknown, or every step fails.

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

    # ── Resolve Etherscan API base (may be None if no key is configured) ─────
    etherscan_base: str | None = None
    if network in _CHAIN_SPECIFIC_APIS:
        api_base, key_env = _CHAIN_SPECIFIC_APIS[network]
        specific_key = os.environ.get(key_env)
        if specific_key:
            etherscan_base = f"{api_base}?apikey={specific_key}"
        else:
            logger.debug("%s not set; Etherscan steps skipped for %s", key_env, network)
    else:
        unified_key = os.environ.get("ETHERSCAN_API_KEY")
        if unified_key:
            etherscan_base = (
                f"https://api.etherscan.io/v2/api"
                f"?chainid={chain_id}&apikey={unified_key}"
            )
        else:
            logger.debug("ETHERSCAN_API_KEY not set; Etherscan steps skipped")

    # ── Resolve RPC URL (may be None if no key / no base for this network) ───
    rpc_api_key = os.environ.get("RPC_API_KEY")
    rpc_base = _ALCHEMY_RPC_BASES.get(network)
    rpc_url: str | None = (
        f"{rpc_base}{rpc_api_key}" if (rpc_api_key and rpc_base) else None
    )

    # Nothing can be done without at least one key
    if not etherscan_base and not rpc_url:
        logger.debug(
            "No API keys available; skipping deployment block lookup for %s on %s",
            address, network,
        )
        return None

    tx_hash: str | None = None  # accumulated across steps for later use

    # ── Steps 1, 1b, 2, 3: Etherscan path ────────────────────────────────────
    if etherscan_base:
        # ── Step 1: getcontractcreation ──────────────────────────────────────
        step1_ok = False
        try:
            resp = _get(
                f"{etherscan_base}&module=contract&action=getcontractcreation"
                f"&contractaddresses={address}",
            )
            resp.raise_for_status()
            data = resp.json()
            creation_result = data.get("result")

            if (
                data.get("status") == "1"
                and isinstance(creation_result, list)
                and creation_result
            ):
                first = creation_result[0]
                if isinstance(first, dict):
                    tx_hash = first.get("txHash") or None
                    step1_ok = bool(tx_hash)

                    # ── Step 1b: blockNumber in the creation payload ──────────
                    block_str = first.get("blockNumber")
                    if block_str:
                        try:
                            block = (
                                int(block_str, 16)
                                if str(block_str).startswith("0x")
                                else int(block_str)
                            )
                            if block > 0:
                                logger.info(
                                    "Auto-detected startBlock %d for %s on %s"
                                    " (from creation response)",
                                    block, address, network,
                                )
                                return block
                        except (ValueError, TypeError):
                            logger.debug(
                                "Could not parse blockNumber %r from creation result",
                                block_str,
                            )
            else:
                logger.warning(
                    "getcontractcreation returned no usable result for %s on %s: %r",
                    address, network, creation_result,
                )
                # Non-fatal — continue to steps 2-4

        except Exception as exc:
            logger.warning(
                "Failed to fetch contract creation info for %s on %s: %s",
                address, network, exc,
            )
            # Non-fatal — continue to steps 2-4

        # ── Step 2: eth_getTransactionByHash ─────────────────────────────────
        # Only worthwhile when step 1 gave us a tx hash.
        if step1_ok and tx_hash:
            try:
                resp = _get(
                    f"{etherscan_base}&module=proxy&action=eth_getTransactionByHash"
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
                logger.warning(
                    "eth_getTransactionByHash failed for tx %s on %s: %s",
                    tx_hash, network, exc,
                )

        # ── Step 3: txlistinternal / txlist ───────────────────────────────────
        # These only need the contract address — no tx hash required.  They
        # work even when step 1 failed entirely (e.g. "Free API access not
        # supported for this chain").
        for action in ("txlistinternal", "txlist"):
            try:
                resp = _get(
                    f"{etherscan_base}&module=account&action={action}"
                    f"&address={address}&startblock=0&endblock=99999999"
                    f"&page=1&offset=1&sort=asc",
                )
                resp.raise_for_status()
                list_data = resp.json()
                if list_data.get("status") == "1":
                    txs = list_data.get("result", [])
                    if txs and isinstance(txs[0], dict):
                        # Always capture the hash for the RPC fallback (step 4a),
                        # even when blockNumber is absent — it may still help.
                        if not tx_hash:
                            tx_hash = txs[0].get("hash") or None
                        block_str = txs[0].get("blockNumber", "")
                        if block_str:
                            block = int(block_str)  # txlist returns decimal strings
                            logger.info(
                                "Auto-detected startBlock %d for %s on %s (via %s)",
                                block, address, network, action,
                            )
                            return block
                logger.debug("%s returned no results for %s on %s", action, address, network)
            except Exception as exc:
                logger.warning(
                    "%s fallback failed for %s on %s: %s", action, address, network, exc
                )

    # ── Step 4: RPC fallback ──────────────────────────────────────────────────
    # Tried when (a) Etherscan steps all failed, or (b) no Etherscan key was
    # configured at all.  Two sub-steps:
    #   4a. eth_getTransactionByHash — fast single call if we have a tx hash.
    #   4b. eth_getCode binary search — works with no tx hash at all.
    if rpc_url:
        if tx_hash:
            block = _rpc_get_tx_block(rpc_url, tx_hash)
            if block is not None:
                logger.info(
                    "Auto-detected startBlock %d for %s on %s (via RPC tx lookup)",
                    block, address, network,
                )
                return block

        # Binary search: no tx hash needed — only address + RPC endpoint.
        block = _rpc_find_deployment_block(rpc_url, address)
        if block is not None:
            logger.info(
                "Auto-detected startBlock %d for %s on %s (via RPC binary search)",
                block, address, network,
            )
            return block

        logger.warning("RPC fallback also failed for %s on %s", address, network)
    else:
        if not rpc_api_key:
            logger.debug(
                "RPC_API_KEY not set; RPC fallback skipped for %s on %s", address, network
            )
        else:
            logger.debug("No Alchemy RPC base configured for network %r", network)

    logger.warning(
        "Could not auto-detect startBlock for %s on %s after all methods exhausted",
        address, network,
    )
    return None
