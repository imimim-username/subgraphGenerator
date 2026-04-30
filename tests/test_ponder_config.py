"""Tests for generate/ponder_config.py — render_ponder_config and helpers."""

import pytest
from subgraph_wizard.generate.ponder_config import render_ponder_config

# ── Helpers ────────────────────────────────────────────────────────────────────

def _cfg(
    networks=None,
    nodes=None,
    ponder_settings=None,
):
    return {
        "schema_version": 1,
        "subgraph_name": "test",
        "networks": networks or [],
        "nodes": nodes or [],
        "edges": [],
        "ponder_settings": ponder_settings or {},
    }


def _net(network, contracts=None, pollingInterval=None, maxBlockRange=None):
    entry = {"network": network, "contracts": contracts or {}}
    if pollingInterval is not None:
        entry["pollingInterval"] = pollingInterval
    if maxBlockRange is not None:
        entry["ethGetLogsBlockRange"] = maxBlockRange  # correct Ponder option name
    return entry


def _contract_instances(*instances):
    """Return a contracts dict for a single contract called 'Token'."""
    return {"Token": {"instances": list(instances)}}


def _inst(address="0xABC", startBlock=0, endBlock=None):
    inst = {"label": "main", "address": address, "startBlock": startBlock}
    if endBlock is not None:
        inst["endBlock"] = endBlock
    return inst


def _contract_node(name, **flags):
    """Build a contract-type node with optional ponder flags."""
    data = {"name": name, "abi": [], "events": [], "readFunctions": []}
    data.update(flags)
    return {"id": f"cn-{name}", "type": "contract", "position": {}, "data": data}


# ── Basic structure ────────────────────────────────────────────────────────────

class TestBasicStructure:
    def test_imports_and_createconfig(self):
        out = render_ponder_config(_cfg())
        assert 'import { createConfig } from "ponder"' in out
        assert "export default createConfig({" in out

    def test_no_networks_defaults_mainnet(self):
        out = render_ponder_config(_cfg())
        assert "mainnet:" in out
        assert "id: 1," in out

    def test_single_network_chain_emitted(self):
        out = render_ponder_config(_cfg(
            networks=[_net("optimism", _contract_instances(_inst("0xDEAD", 100)))]
        ))
        assert "optimismMainnet:" in out or "optimism:" in out  # slug → camelCase
        assert "id: 10," in out
        assert "PONDER_RPC_URL_10" in out

    def test_hyphenated_slug_camelcased(self):
        out = render_ponder_config(_cfg(
            networks=[_net("arbitrum-one", _contract_instances(_inst()))]
        ))
        assert "arbitrumOne:" in out

    def test_unknown_slug_chain_id_zero(self):
        out = render_ponder_config(_cfg(
            networks=[_net("custom-chain", _contract_instances(_inst()))]
        ))
        assert "id: 0," in out

    def test_abi_import_generated(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))],
        ))
        assert 'import { TokenAbi } from "./abis/TokenAbi"' in out

    def test_contract_address_emitted(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst("0x1234567890abcdef1234567890abcdef12345678")))]
        ))
        assert "0x1234567890abcdef1234567890abcdef12345678" in out

    def test_empty_address_fallback_null_address(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(address="")))]
        ))
        assert "0x0000000000000000000000000000000000000000" in out

    def test_startblock_emitted_when_nonzero(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(startBlock=12345678)))]
        ))
        assert "startBlock: 12345678" in out

    def test_startblock_omitted_when_zero(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(startBlock=0)))]
        ))
        assert "startBlock" not in out

    def test_startblock_string_parsed(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(startBlock="99999")))]
        ))
        assert "startBlock: 99999" in out

    def test_invalid_startblock_defaults_zero(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(startBlock="bad")))]
        ))
        assert "startBlock" not in out


# ── endBlock ───────────────────────────────────────────────────────────────────

class TestEndBlock:
    def test_endblock_emitted(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(endBlock=15_000_000)))]
        ))
        assert "endBlock: 15000000" in out

    def test_endblock_string_parsed(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(endBlock="15000000")))]
        ))
        assert "endBlock: 15000000" in out

    def test_endblock_omitted_when_absent(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))]
        ))
        assert "endBlock" not in out

    def test_endblock_omitted_when_empty_string(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(endBlock="")))]
        ))
        assert "endBlock" not in out

    def test_invalid_endblock_omitted(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst(endBlock="garbage")))]
        ))
        assert "endBlock" not in out


# ── includeCallTraces / includeTransactionReceipts ─────────────────────────────

class TestPerContractFlags:
    def test_include_call_traces(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))],
            nodes=[_contract_node("Token", includeCallTraces=True)],
        ))
        assert "includeCallTraces: true" in out

    def test_include_transaction_receipts(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))],
            nodes=[_contract_node("Token", includeTransactionReceipts=True)],
        ))
        assert "includeTransactionReceipts: true" in out

    def test_flags_omitted_when_false(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))],
            nodes=[_contract_node("Token", includeCallTraces=False, includeTransactionReceipts=False)],
        ))
        assert "includeCallTraces" not in out
        assert "includeTransactionReceipts" not in out

    def test_flags_omitted_when_no_node(self):
        """Flags come from contract node data — absent node means no flags."""
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))],
        ))
        assert "includeCallTraces" not in out
        assert "includeTransactionReceipts" not in out

    def test_both_flags_together(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))],
            nodes=[_contract_node("Token", includeCallTraces=True, includeTransactionReceipts=True)],
        ))
        assert "includeCallTraces: true" in out
        assert "includeTransactionReceipts: true" in out


# ── Per-chain advanced options ─────────────────────────────────────────────────

class TestPerChainOptions:
    def test_polling_interval_emitted(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()), pollingInterval=2000)]
        ))
        assert "pollingInterval: 2000" in out

    def test_eth_get_logs_block_range_emitted(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()), maxBlockRange=500)]
        ))
        assert "ethGetLogsBlockRange: 500" in out

    def test_both_advanced_chain_options(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()), pollingInterval=1000, maxBlockRange=250)]
        ))
        assert "pollingInterval: 1000" in out
        assert "ethGetLogsBlockRange: 250" in out

    def test_chain_options_omitted_when_absent(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))]
        ))
        assert "pollingInterval" not in out
        assert "ethGetLogsBlockRange" not in out

    def test_chain_options_string_values_parsed(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()), pollingInterval="3000", maxBlockRange="1000")]
        ))
        assert "pollingInterval: 3000" in out
        assert "ethGetLogsBlockRange: 1000" in out

    def test_invalid_chain_options_omitted(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()), pollingInterval="bad", maxBlockRange="")]
        ))
        assert "pollingInterval" not in out
        assert "ethGetLogsBlockRange" not in out

    def test_chain_options_only_on_correct_chain(self):
        """Options set on mainnet should not bleed onto optimism."""
        out = render_ponder_config(_cfg(
            networks=[
                _net("mainnet", _contract_instances(_inst()), pollingInterval=1000),
                _net("optimism", {"Widget": {"instances": [_inst("0xBBB")]}}),
            ]
        ))
        # pollingInterval should be inside mainnet block only
        mainnet_section = out.split("optimism")[0]
        assert "pollingInterval: 1000" in mainnet_section


# ── database block ─────────────────────────────────────────────────────────────

class TestDatabaseBlock:
    def test_pglite_no_database_block(self):
        out = render_ponder_config(_cfg(ponder_settings={"database": "pglite"}))
        assert "database:" not in out

    def test_default_no_database_block(self):
        out = render_ponder_config(_cfg(ponder_settings={}))
        assert "database:" not in out

    def test_postgres_emits_database_block(self):
        out = render_ponder_config(_cfg(ponder_settings={"database": "postgres"}))
        assert 'database: {' in out
        assert 'kind: "postgres"' in out
        assert "process.env.DATABASE_URL" in out

    def test_postgres_block_before_chains(self):
        out = render_ponder_config(_cfg(ponder_settings={"database": "postgres"}))
        db_pos = out.index("database:")
        chains_pos = out.index("chains:")
        assert db_pos < chains_pos


# ── ordering ──────────────────────────────────────────────────────────────────

class TestOrdering:
    def test_multichain_ordering_omitted(self):
        """multichain is Ponder's default — no need to emit it."""
        out = render_ponder_config(_cfg(ponder_settings={"ordering": "multichain"}))
        assert "ordering:" not in out

    def test_default_ordering_omitted(self):
        """Empty ponder_settings → multichain is the implicit default."""
        out = render_ponder_config(_cfg(ponder_settings={}))
        assert "ordering:" not in out

    def test_omnichain_ordering_emitted(self):
        """omnichain is non-default, so it must be emitted explicitly."""
        out = render_ponder_config(_cfg(ponder_settings={"ordering": "omnichain"}))
        assert 'ordering: "omnichain"' in out

    def test_experimental_isolated_ordering_emitted(self):
        out = render_ponder_config(_cfg(ponder_settings={"ordering": "experimental_isolated"}))
        assert 'ordering: "experimental_isolated"' in out

    def test_ordering_before_chains(self):
        out = render_ponder_config(_cfg(ponder_settings={"ordering": "omnichain"}))
        ord_pos = out.index("ordering:")
        chains_pos = out.index("chains:")
        assert ord_pos < chains_pos


# ── Multi-network / second-pass contract nodes ────────────────────────────────

class TestMultiNetworkAndFallback:
    def test_two_networks_both_chains_emitted(self):
        out = render_ponder_config(_cfg(
            networks=[
                _net("mainnet", _contract_instances(_inst("0xAAA", 100))),
                _net("optimism", _contract_instances(_inst("0xBBB", 200))),
            ]
        ))
        assert "mainnet:" in out
        assert "optimism:" in out or "optimismMainnet:" in out

    def test_contract_not_in_networks_still_emitted(self):
        """Contract nodes with no Networks panel entry appear as placeholders."""
        out = render_ponder_config(_cfg(
            nodes=[_contract_node("Orphan")],
        ))
        assert "Orphan:" in out
        assert "OrphanAbi" in out

    def test_multiple_instances_comment_added(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", {
                "Token": {
                    "instances": [
                        _inst("0xAAA", 100),
                        _inst("0xBBB", 200),
                    ]
                }
            })],
        ))
        assert "additional instance" in out

    def test_complete_config_structure(self):
        """Smoke test for a realistic complete config."""
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst("0xDEAD", 14_000_000, endBlock=15_000_000)), pollingInterval=2000)],
            nodes=[_contract_node("Token", includeCallTraces=True)],
            ponder_settings={"database": "postgres", "ordering": "omnichain"},
        ))
        assert 'kind: "postgres"' in out
        assert 'ordering: "omnichain"' in out  # omnichain is non-default, so it's emitted
        assert "pollingInterval: 2000" in out
        assert "startBlock: 14000000" in out
        assert "endBlock: 15000000" in out
        assert "includeCallTraces: true" in out
        assert "createConfig" in out


# ── Multi-network, same contract on different chains ──────────────────────────

class TestMultiNetworkSameContract:
    """A contract deployed on two different networks should appear on both chains
    and have two separate chain entries. This exercises the instance-grouping
    logic that handles the same contract type across multiple networks."""

    def _two_network_cfg(self):
        return _cfg(
            networks=[
                _net("mainnet",  {"Token": {"instances": [_inst("0xAAAA", 14_000_000)]}}),
                _net("optimism", {"Token": {"instances": [_inst("0xBBBB",  1_000_000)]}}),
            ]
        )

    def test_both_chains_emitted(self):
        out = render_ponder_config(self._two_network_cfg())
        assert "mainnet:" in out
        assert "optimism:" in out

    def test_mainnet_chain_id(self):
        out = render_ponder_config(self._two_network_cfg())
        assert "id: 1," in out

    def test_optimism_chain_id(self):
        out = render_ponder_config(self._two_network_cfg())
        assert "id: 10," in out

    def test_both_rpc_env_vars(self):
        out = render_ponder_config(self._two_network_cfg())
        assert "PONDER_RPC_URL_1" in out
        assert "PONDER_RPC_URL_10" in out

    def test_contract_section_exists(self):
        out = render_ponder_config(self._two_network_cfg())
        assert "Token:" in out
        assert "TokenAbi" in out

    def test_multi_chain_object_format(self):
        """Multi-chain deployment uses chain: { mainnet: {...}, optimism: {...} } format."""
        out = render_ponder_config(self._two_network_cfg())
        # chain must be an object, not a string
        assert 'chain: "' not in out.split("Token:")[1]
        assert "chain: {" in out

    def test_both_addresses_in_output(self):
        """Both chain-specific addresses should appear in the multi-chain format."""
        out = render_ponder_config(self._two_network_cfg())
        assert "0xAAAA" in out
        assert "0xBBBB" in out

    def test_three_networks_all_chains_emitted(self):
        cfg = _cfg(
            networks=[
                _net("mainnet",     {"Token": {"instances": [_inst("0xAAA")]}}),
                _net("optimism",    {"Token": {"instances": [_inst("0xBBB")]}}),
                _net("arbitrum-one",{"Token": {"instances": [_inst("0xCCC")]}}),
            ]
        )
        out = render_ponder_config(cfg)
        assert "mainnet:" in out
        assert "optimism:" in out
        assert "arbitrumOne:" in out
        assert "id: 42161," in out  # arbitrum-one chain ID
