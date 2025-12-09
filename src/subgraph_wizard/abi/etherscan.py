"""Fetch ABI from Etherscan-compatible explorers."""

import json
import logging
import os
from typing import Any

import requests

from subgraph_wizard.errors import AbiFetchError
from subgraph_wizard.networks import SUPPORTED_NETWORKS

logger = logging.getLogger(__name__)

# Timeout for API requests in seconds
REQUEST_TIMEOUT = 10

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
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
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
