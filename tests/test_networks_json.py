"""Tests for generate/networks_json.py."""

import json
import pytest

from subgraph_wizard.generate.networks_json import build_networks_json, render_networks_json

# ── Fixtures ─────────────────────────────────────────────────────────────────

SINGLE_NETWORK = [
    {
        "network": "mainnet",
        "contracts": {
            "ERC20": {
                "instances": [
                    {"label": "myToken", "address": "0xAAA", "startBlock": 1000}
                ]
            }
        },
    }
]

MULTI_INSTANCE = [
    {
        "network": "mainnet",
        "contracts": {
            "Alchemist": {
                "instances": [
                    {"label": "alUSD", "address": "0xAAA", "startBlock": 14265505},
                    {"label": "alETH", "address": "0xBBB", "startBlock": 14265505},
                ]
            }
        },
    }
]

MULTI_NETWORK = [
    {
        "network": "mainnet",
        "contracts": {
            "Alchemist": {
                "instances": [{"label": "alUSD", "address": "0xAAA", "startBlock": 100}]
            }
        },
    },
    {
        "network": "arbitrum-one",
        "contracts": {
            "Alchemist": {
                "instances": [{"label": "alUSD", "address": "0xCCC", "startBlock": 200}]
            }
        },
    },
]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBuildNetworksJson:
    def test_produces_network_key(self):
        result = build_networks_json(SINGLE_NETWORK)
        assert "mainnet" in result

    def test_produces_datasource_key(self):
        result = build_networks_json(SINGLE_NETWORK)
        assert "ERC20_myToken" in result["mainnet"]

    def test_address_included(self):
        result = build_networks_json(SINGLE_NETWORK)
        assert result["mainnet"]["ERC20_myToken"]["address"] == "0xAAA"

    def test_start_block_included_as_int(self):
        result = build_networks_json(SINGLE_NETWORK)
        assert result["mainnet"]["ERC20_myToken"]["startBlock"] == 1000

    def test_multi_instance_produces_separate_keys(self):
        result = build_networks_json(MULTI_INSTANCE)
        network = result["mainnet"]
        assert "Alchemist_alUSD" in network
        assert "Alchemist_alETH" in network

    def test_multi_instance_addresses_correct(self):
        result = build_networks_json(MULTI_INSTANCE)
        assert result["mainnet"]["Alchemist_alUSD"]["address"] == "0xAAA"
        assert result["mainnet"]["Alchemist_alETH"]["address"] == "0xBBB"

    def test_multi_network(self):
        result = build_networks_json(MULTI_NETWORK)
        assert "mainnet" in result
        assert "arbitrum-one" in result
        assert result["mainnet"]["Alchemist_alUSD"]["address"] == "0xAAA"
        assert result["arbitrum-one"]["Alchemist_alUSD"]["address"] == "0xCCC"

    def test_empty_config_returns_empty(self):
        assert build_networks_json([]) == {}

    def test_missing_label_instance_skipped(self):
        config = [
            {
                "network": "mainnet",
                "contracts": {
                    "Token": {
                        "instances": [{"label": "", "address": "0xDDD", "startBlock": 1}]
                    }
                },
            }
        ]
        result = build_networks_json(config)
        # No entry should be created (label is required)
        assert result.get("mainnet", {}) == {}

    def test_string_start_block_converted(self):
        config = [
            {
                "network": "mainnet",
                "contracts": {
                    "Token": {
                        "instances": [{"label": "t", "address": "0x1", "startBlock": "99"}]
                    }
                },
            }
        ]
        result = build_networks_json(config)
        assert result["mainnet"]["Token_t"]["startBlock"] == 99

    def test_invalid_start_block_omitted(self):
        config = [
            {
                "network": "mainnet",
                "contracts": {
                    "Token": {
                        "instances": [{"label": "t", "address": "0x1", "startBlock": "bad"}]
                    }
                },
            }
        ]
        result = build_networks_json(config)
        assert "startBlock" not in result["mainnet"]["Token_t"]


class TestRenderNetworksJson:
    def test_returns_valid_json(self):
        output = render_networks_json(SINGLE_NETWORK)
        parsed = json.loads(output)
        assert "mainnet" in parsed

    def test_pretty_printed(self):
        output = render_networks_json(SINGLE_NETWORK)
        assert "\n" in output
