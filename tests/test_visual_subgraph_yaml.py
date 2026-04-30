"""Tests for render_visual_subgraph_yaml in generate/subgraph_yaml.py.

Focuses on the visual-editor code path (render_visual_subgraph_yaml), which
generates subgraph.yaml from a visual-config.json node/edge graph.
"""

import pytest
from subgraph_wizard.generate.subgraph_yaml import render_visual_subgraph_yaml


# ── Minimal config helpers ─────────────────────────────────────────────────────

def _make_config(nodes, edges, subgraph_name="test-subgraph"):
    return {
        "schema_version": 1,
        "subgraph_name": subgraph_name,
        "networks": [],
        "nodes": nodes,
        "edges": edges,
    }


def _contract_node(node_id, name, events=None, address="0x1234", network="mainnet", start_block=100):
    return {
        "id": node_id,
        "type": "contract",
        "position": {"x": 0, "y": 0},
        "data": {
            "name": name,
            "address": address,
            "network": network,
            "startBlock": start_block,
            "abi": [],
            "events": events or [],
            "readFunctions": [],
            "instances": [],
        },
    }


def _entity_node(node_id, name, fields=None):
    return {
        "id": node_id,
        "type": "entity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
        },
    }


def _agg_node(node_id, name, fields=None):
    return {
        "id": node_id,
        "type": "aggregateentity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
        },
    }


def _edge(edge_id, source, source_handle, target, target_handle):
    return {
        "id": edge_id,
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": target_handle,
    }


DEPOSIT_EVENT = {
    "name": "Deposit",
    "signature": "Deposit(address,uint256)",
    "params": [{"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"}],
}

TRANSFER_EVENT = {
    "name": "Transfer",
    "signature": "Transfer(address,address,uint256)",
    "params": [{"name": "value", "solidity_type": "uint256", "graph_type": "BigInt"}],
}


# ── Handler filtering: only include events with compiled handler functions ──────

class TestYamlHandlerFiltering:
    """The eventHandlers section must only reference events that have handler
    functions in the mapping file.  Including a non-existent handler causes
    `graph build` to fail."""

    def test_unwired_event_excluded_from_yaml(self):
        """Transfer has no entity wire — its handler must NOT appear in the YAML."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT, TRANSFER_EVENT])
        entity = _entity_node("e1", "Record")
        # Only Deposit is wired
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "handleTransfer" not in yaml, (
            "Unwired Transfer handler must not appear in subgraph.yaml"
        )
        assert "handleDeposit" in yaml, "Wired Deposit handler must appear"

    def test_wired_event_included_in_yaml(self):
        """Both events wired — both handlers appear."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT, TRANSFER_EVENT])
        entity_a = _entity_node("ea", "DepRec")
        entity_b = _entity_node("eb", "TxRec")
        edges = [
            _edge("e1", "c1", "event-Deposit",  "ea", "field-id"),
            _edge("e2", "c1", "event-Transfer",  "eb", "field-id"),
        ]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity_a, entity_b], edges))
        assert "handleDeposit" in yaml
        assert "handleTransfer" in yaml

    def test_no_wired_events_produces_no_event_handlers(self):
        """Contract with events but no wired entities → no eventHandlers section."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        # No entities at all
        yaml = render_visual_subgraph_yaml(_make_config([contract], []))
        assert "handleDeposit" not in yaml

    def test_trigger_events_checklist_includes_handler_in_yaml(self):
        """Aggregate wired via triggerEvents checklist (no direct edge) — handler must appear."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        agg = {
            "id": "agg1",
            "type": "aggregateentity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "VaultTVL",
                "fields": [{"name": "id", "type": "ID", "required": True}],
                "triggerEvents": [
                    {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}
                ],
            },
        }
        edges = [_edge("e1", "c1", "implicit-address", "agg1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, agg], edges))
        assert "handleDeposit" in yaml


# ── General correctness ────────────────────────────────────────────────────────

class TestYamlGeneralCorrectness:
    def test_basic_structure_present(self):
        """Generated YAML has required top-level keys."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "specVersion:" in yaml
        assert "dataSources:" in yaml
        assert "schema:" in yaml

    def test_contract_address_embedded(self):
        """The contract address appears in the generated YAML."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT],
                                  address="0xDeadBeef")
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "0xDeadBeef" in yaml

    def test_start_block_embedded(self):
        """The startBlock value appears in the generated YAML."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT], start_block=9999)
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "9999" in yaml

    def test_network_embedded(self):
        """The network value appears in the generated YAML."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT], network="arbitrum-one")
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "arbitrum-one" in yaml

    def test_mapping_file_path(self):
        """The mapping file path points to src/mappings/{ContractType}.ts."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "src/mappings/Token.ts" in yaml

    def test_abi_path_includes_abis_dir(self):
        """The ABI file path references the ./abis/ directory."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "./abis/Token.json" in yaml

    def test_event_signature_in_handler(self):
        """The event signature appears correctly in eventHandlers."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "Deposit(address,uint256)" in yaml

    def test_no_contract_empty_name_skipped(self):
        """Contract nodes with empty names are silently skipped."""
        bad_contract = _contract_node("c0", "", events=[DEPOSIT_EVENT])
        good_contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(
            _make_config([bad_contract, good_contract, entity], edges)
        )
        # Good contract should still appear
        assert "Token" in yaml
        # No empty datasource name
        assert "name: \n" not in yaml

    def test_entity_names_listed(self):
        """Entity type names appear in the entities list."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "MyRecord")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "MyRecord" in yaml


# ── Networks tab address/startBlock injection ─────────────────────────────────

class TestYamlNetworksConfig:
    """Addresses and startBlocks set in the Networks tab must appear in the
    generated YAML — not the zero address fallback."""

    def _config_with_networks(self, network="mainnet"):
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        networks = [
            {
                "network": network,
                "contracts": {
                    "Token": {
                        "instances": [
                            {"label": "", "address": "0xDeadBeef1234", "startBlock": 7777}
                        ]
                    }
                },
            }
        ]
        cfg = _make_config([contract, entity], edges)
        cfg["networks"] = networks
        return cfg

    def test_networks_address_used(self):
        """Address from the Networks tab appears instead of the zero fallback."""
        yaml = render_visual_subgraph_yaml(self._config_with_networks())
        assert "0xDeadBeef1234" in yaml
        assert "0x0000000000000000000000000000000000000000" not in yaml

    def test_networks_start_block_used(self):
        """startBlock from the Networks tab appears in the YAML."""
        yaml = render_visual_subgraph_yaml(self._config_with_networks())
        assert "7777" in yaml

    def test_networks_network_name_used(self):
        """Network name from the Networks tab entry is used."""
        yaml = render_visual_subgraph_yaml(self._config_with_networks(network="arbitrum-one"))
        assert "arbitrum-one" in yaml

    def test_multiple_instances_produce_multiple_datasources(self):
        """Multiple instances in the Networks tab produce multiple data sources."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        networks = [
            {
                "network": "mainnet",
                "contracts": {
                    "Token": {
                        "instances": [
                            {"label": "alpha", "address": "0xAAAA", "startBlock": 100},
                            {"label": "beta",  "address": "0xBBBB", "startBlock": 200},
                        ]
                    }
                },
            }
        ]
        cfg = _make_config([contract, entity], edges)
        cfg["networks"] = networks
        yaml = render_visual_subgraph_yaml(cfg)
        assert "0xAAAA" in yaml
        assert "0xBBBB" in yaml
        # First instance is named bare contract_type; second gets the label suffix.
        assert "name: Token\n" in yaml or "name: Token" in yaml
        assert "Token_beta" in yaml

    def test_no_networks_falls_back_to_node_address(self):
        """When no networks config is present, node-level address is used."""
        contract = _contract_node("c1", "Token", events=[DEPOSIT_EVENT], address="0xNodeAddr")
        entity = _entity_node("e1", "Record")
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        yaml = render_visual_subgraph_yaml(_make_config([contract, entity], edges))
        assert "0xNodeAddr" in yaml
