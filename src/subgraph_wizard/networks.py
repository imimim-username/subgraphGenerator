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
