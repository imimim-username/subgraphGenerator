"""Network metadata and configuration."""

import logging

logger = logging.getLogger(__name__)

SUPPORTED_NETWORKS = {
    "ethereum": {
        "explorer": "api.etherscan.io",
        "chain_id": 1,
        "default_start_block": 0
    },
    "optimism": {
        "explorer": "api-optimistic.etherscan.io",
        "chain_id": 10,
        "default_start_block": 0
    },
    "arbitrum": {
        "explorer": "api.arbiscan.io",
        "chain_id": 42161,
        "default_start_block": 0
    },
}

# Mapping from graph-cli / visual-editor network names to Ethereum chain IDs.
# Used with the Etherscan v2 unified API (one key covers all chains).
GRAPH_NETWORK_CHAIN_IDS: dict[str, int] = {
    "mainnet":          1,
    "goerli":           5,
    "sepolia":          11155111,
    "optimism":         10,
    "optimism-goerli":  420,
    "arbitrum-one":     42161,
    "arbitrum-goerli":  421613,
    "polygon":          137,
    "mumbai":           80001,
    "base":             8453,
    "base-goerli":      84531,
    "bnb":              56,
    "avalanche":        43114,
    "gnosis":           100,
    "linea":            59144,
    "scroll":           534352,
    "zksync-era":       324,
    "celo":             42220,
    # Legacy keys kept for backward compatibility with SUPPORTED_NETWORKS
    "ethereum":         1,
    "arbitrum":         42161,
}
