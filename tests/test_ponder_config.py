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


# ── startBlock — Etherscan auto-detection integration ──────────────────────────

class TestStartBlockEtherscanIntegration:
    """Verify that render_ponder_config calls get_contract_deployment_block when
    startBlock is 0 and a real address is present, then uses the result.

    All network calls are mocked so no real API key is needed.
    """

    # The function is lazily imported inside the ponder_config body, so we must
    # patch it at its *source* module, not at the ponder_config namespace.
    _TARGET = "subgraph_wizard.abi.etherscan.get_contract_deployment_block"

    def test_etherscan_detected_block_emitted(self, monkeypatch):
        """When Etherscan returns a block number it must appear in the output."""
        from unittest.mock import patch
        with patch(self._TARGET, return_value=14_265_505) as mock_fn:
            out = render_ponder_config(_cfg(
                networks=[_net("mainnet", _contract_instances(
                    _inst(address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", startBlock=0)
                ))]
            ))
        mock_fn.assert_called_once()
        assert "startBlock: 14265505" in out

    def test_etherscan_failure_omits_startblock(self, monkeypatch):
        """When Etherscan returns None (failure/no key) no startBlock is emitted."""
        from unittest.mock import patch
        with patch(self._TARGET, return_value=None):
            out = render_ponder_config(_cfg(
                networks=[_net("mainnet", _contract_instances(
                    _inst(address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", startBlock=0)
                ))]
            ))
        assert "startBlock" not in out

    def test_etherscan_not_called_for_zero_address(self):
        """Zero address (0x000…) must not trigger an Etherscan lookup."""
        from unittest.mock import patch
        zero = "0x0000000000000000000000000000000000000000"
        with patch(self._TARGET) as mock_fn:
            render_ponder_config(_cfg(
                networks=[_net("mainnet", _contract_instances(
                    _inst(address=zero, startBlock=0)
                ))]
            ))
        mock_fn.assert_not_called()

    def test_etherscan_not_called_for_empty_address(self):
        """Empty address must not trigger an Etherscan lookup."""
        from unittest.mock import patch
        with patch(self._TARGET) as mock_fn:
            render_ponder_config(_cfg(
                networks=[_net("mainnet", _contract_instances(
                    _inst(address="", startBlock=0)
                ))]
            ))
        mock_fn.assert_not_called()

    def test_etherscan_not_called_when_startblock_already_set(self):
        """If the user already set a startBlock, Etherscan must not be called."""
        from unittest.mock import patch
        with patch(self._TARGET) as mock_fn:
            render_ponder_config(_cfg(
                networks=[_net("mainnet", _contract_instances(
                    _inst(address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", startBlock=99999)
                ))]
            ))
        mock_fn.assert_not_called()

    def test_etherscan_called_per_instance_not_per_contract(self):
        """Each instance with startBlock=0 triggers one Etherscan call."""
        from unittest.mock import patch
        with patch(self._TARGET, side_effect=[10_000_000, 20_000_000]) as mock_fn:
            render_ponder_config(_cfg(
                networks=[_net("mainnet", {"Token": {"instances": [
                    {"label": "a", "address": "0xAAAA", "startBlock": 0},
                    {"label": "b", "address": "0xBBBB", "startBlock": 0},
                ]}})]
            ))
        assert mock_fn.call_count == 2

    def test_multichain_per_chain_startblock_emitted(self):
        """Multi-chain format: each chain's startBlock appears inside its sub-object."""
        from unittest.mock import patch
        with patch(self._TARGET, return_value=None):
            out = render_ponder_config(_cfg(
                networks=[
                    _net("mainnet",  {"Token": {"instances": [_inst("0xAAA", startBlock=14_000_000)]}}),
                    _net("optimism", {"Token": {"instances": [_inst("0xBBB", startBlock=0)]}})
                ]
            ))
        # mainnet instance has an explicit startBlock — must appear in output
        assert "startBlock: 14000000" in out
        # optimism instance has startBlock=0 — must not emit any startBlock
        # (check by inspecting the contracts section directly)
        contracts_section = out[out.index("contracts:"):]
        # Inside the contracts section, mainnet has startBlock but optimism does not
        mainnet_chunk_start = contracts_section.index("mainnet:")
        optimism_chunk_start = contracts_section.index("optimism:")
        mainnet_chunk = contracts_section[mainnet_chunk_start:optimism_chunk_start]
        assert "startBlock: 14000000" in mainnet_chunk
        optimism_chunk = contracts_section[optimism_chunk_start:]
        assert "startBlock" not in optimism_chunk


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

    def test_disable_cache_emitted(self):
        net = {"network": "mainnet", "contracts": _contract_instances(_inst()), "disableCache": True}
        out = render_ponder_config(_cfg(networks=[net]))
        assert "disableCache: true" in out

    def test_disable_cache_omitted_when_false(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))]
        ))
        assert "disableCache" not in out

    def test_ws_emitted_when_enabled(self):
        net = {"network": "mainnet", "contracts": _contract_instances(_inst()), "wsEnabled": True}
        out = render_ponder_config(_cfg(networks=[net]))
        assert "ws: process.env.PONDER_WS_URL_1" in out

    def test_ws_omitted_when_disabled(self):
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", _contract_instances(_inst()))]
        ))
        assert "ws:" not in out


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

    def test_multiple_instances_same_chain_address_array(self):
        """Multiple instances on the same chain → address: [...] array syntax."""
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
        assert '"0xAAA"' in out
        assert '"0xBBB"' in out
        # Both addresses should appear inside an array literal
        assert '["0xAAA", "0xBBB"]' in out

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


# ── Multi-address same chain & env example ────────────────────────────────────

class TestMultiAddressAndEnvExample:
    from subgraph_wizard.generate.ponder_config import render_ponder_env_example

    def test_multi_address_same_chain_array(self):
        """Two instances on one chain → address: ["0xAAA", "0xBBB"] array."""
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", {
                "Token": {"instances": [_inst("0xAAA", 100), _inst("0xBBB", 200)]}
            })]
        ))
        assert '["0xAAA", "0xBBB"]' in out

    def test_multi_address_uses_min_start_block(self):
        """startBlock should be the minimum across all same-chain instances."""
        out = render_ponder_config(_cfg(
            networks=[_net("mainnet", {
                "Token": {"instances": [_inst("0xAAA", 500), _inst("0xBBB", 100)]}
            })]
        ))
        assert "startBlock: 100" in out
        assert "startBlock: 500" not in out

    def test_ws_var_in_env_example(self):
        from subgraph_wizard.generate.ponder_config import render_ponder_env_example
        net = {"network": "mainnet", "contracts": {}, "wsEnabled": True}
        out = render_ponder_env_example({"networks": [net]})
        assert "PONDER_WS_URL_1=" in out

    def test_ws_var_absent_when_not_enabled(self):
        from subgraph_wizard.generate.ponder_config import render_ponder_env_example
        out = render_ponder_env_example({"networks": [{"network": "mainnet", "contracts": {}}]})
        assert "PONDER_WS_URL" not in out


# ── render_ponder_api_index ────────────────────────────────────────────────────

class TestRenderPonderApiIndex:
    """Tests for render_ponder_api_index — the src/api/index.ts stub.

    Ponder requires ``src/api/index.ts`` to exist and export a Hono app.
    Missing this file causes a build error:
        "API endpoint file not found. Create a file at src/api/index.ts."
    """

    def test_imports_hono(self):
        """Must import Hono from 'hono' (the HTTP framework bundled with Ponder)."""
        from subgraph_wizard.generate.ponder_config import render_ponder_api_index
        out = render_ponder_api_index()
        assert 'from "hono"' in out or "from 'hono'" in out

    def test_exports_default(self):
        """Must have a default export — Ponder picks it up as the app entry point."""
        from subgraph_wizard.generate.ponder_config import render_ponder_api_index
        out = render_ponder_api_index()
        assert "export default" in out

    def test_is_valid_typescript(self):
        """Basic sanity: no syntax clues that would cause immediate parse errors."""
        from subgraph_wizard.generate.ponder_config import render_ponder_api_index
        out = render_ponder_api_index()
        # Must be a non-empty string
        assert isinstance(out, str) and len(out) > 0
        # No stray Python-isms
        assert "def " not in out
        assert "import " in out  # at least one import

    def test_is_idempotent(self):
        """Calling render_ponder_api_index twice returns identical output."""
        from subgraph_wizard.generate.ponder_config import render_ponder_api_index
        assert render_ponder_api_index() == render_ponder_api_index()

    def test_hono_app_instantiated(self):
        """The file must instantiate a Hono app (new Hono() or Hono())."""
        from subgraph_wizard.generate.ponder_config import render_ponder_api_index
        out = render_ponder_api_index()
        assert "Hono()" in out or "new Hono" in out

    def test_graphql_middleware_mounted(self):
        """Since Ponder 0.8 the GraphQL API is not automatic — must be mounted explicitly.

        Without `app.use("/graphql", graphql({ db, schema }))` every request
        to /graphql returns 404.
        """
        from subgraph_wizard.generate.ponder_config import render_ponder_api_index
        out = render_ponder_api_index()
        # Must import the graphql helper from "ponder"
        assert 'from "ponder"' in out
        assert "graphql" in out
        # Must import db and schema from the virtual modules
        assert 'from "ponder:api"' in out
        assert 'from "ponder:schema"' in out
        # Must mount graphql at /graphql
        assert '"/graphql"' in out
        assert "graphql({ db, schema })" in out

    def test_graphql_also_mounted_at_root(self):
        """Mounting graphql at / lets users open localhost:42069/ directly."""
        from subgraph_wizard.generate.ponder_config import render_ponder_api_index
        out = render_ponder_api_index()
        # Both / and /graphql should serve the playground
        assert '"/"' in out
        assert out.count("graphql({ db, schema })") >= 2


# ── render_ponder_howto — .env.local ──────────────────────────────────────────

class TestHowtoEnvLocal:
    """Verify PONDER_HOWTO.md instructs users to use .env.local, not .env.

    Ponder reads environment variables from .env.local (following the Next.js
    convention).  Using a plain .env file will cause silent failures where RPC
    URLs are undefined and connections fail immediately.
    """

    def test_howto_pglite_uses_env_local(self):
        """PGlite path: HOWTO must say cp .env.example .env.local."""
        from subgraph_wizard.generate.ponder_config import render_ponder_howto
        howto = render_ponder_howto("my-app", "/out", {})
        assert ".env.local" in howto

    def test_howto_postgres_uses_env_local(self):
        """Postgres path: HOWTO must also say .env.local."""
        from subgraph_wizard.generate.ponder_config import render_ponder_howto
        cfg = {"ponder_settings": {"database": "postgres"}}
        howto = render_ponder_howto("my-app", "/out", cfg)
        assert ".env.local" in howto

    def test_howto_pglite_does_not_say_cp_to_plain_env(self):
        """HOWTO must NOT tell users to create a plain .env (would be ignored by Ponder)."""
        from subgraph_wizard.generate.ponder_config import render_ponder_howto
        howto = render_ponder_howto("my-app", "/out", {})
        # 'cp .env.example .env' followed by a newline or backtick = wrong instruction
        assert "cp .env.example .env\n" not in howto
        assert "cp .env.example .env`" not in howto

    def test_howto_postgres_does_not_say_cp_to_plain_env(self):
        """Postgres path HOWTO must also not say 'cp .env.example .env'."""
        from subgraph_wizard.generate.ponder_config import render_ponder_howto
        cfg = {"ponder_settings": {"database": "postgres"}}
        howto = render_ponder_howto("my-app", "/out", cfg)
        assert "cp .env.example .env\n" not in howto
        assert "cp .env.example .env`" not in howto

    def test_howto_env_local_note_present(self):
        """HOWTO must include an explicit note that Ponder reads .env.local."""
        from subgraph_wizard.generate.ponder_config import render_ponder_howto
        howto = render_ponder_howto("my-app", "/out", {})
        # Should contain something like "Ponder reads .env.local"
        assert ".env.local" in howto and ".env.example" in howto


# ── CHAIN_IDS coverage ────────────────────────────────────────────────────────

class TestChainIds:
    """Regression: frontend KNOWN_NETWORKS slugs must all be in CHAIN_IDS."""

    from subgraph_wizard.generate.ponder_config import CHAIN_IDS

    # These are the slugs the frontend dropdown can produce.
    FRONTEND_SLUGS = [
        "mainnet", "sepolia", "holesky",
        "optimism", "optimism-sepolia",
        "base", "base-sepolia",
        "zora", "mode", "blast", "fraxtal", "cyber", "redstone",
        "arbitrum-one", "arbitrum-sepolia",
        "polygon", "amoy",
        "bnb", "bsc-testnet",
        "avalanche", "fuji",
        "gnosis", "gnosis-chiado",
        "zksync-era", "zksync-sepolia",
        "linea", "linea-sepolia",
        "scroll", "scroll-sepolia",
        "mantle", "celo", "fantom",
        # Legacy / still-used
        "mumbai", "goerli", "optimism-goerli", "arbitrum-goerli", "base-goerli",
    ]

    def test_all_frontend_slugs_have_chain_id(self):
        """Every slug the UI dropdown can produce must have a non-zero chain ID."""
        from subgraph_wizard.generate.ponder_config import CHAIN_IDS
        missing = [s for s in self.FRONTEND_SLUGS if CHAIN_IDS.get(s, 0) == 0]
        assert missing == [], f"Slugs missing from CHAIN_IDS: {missing}"

    def test_mumbai_resolves_correctly(self):
        """Frontend uses 'mumbai' (not 'polygon-mumbai') — must resolve to 80001."""
        from subgraph_wizard.generate.ponder_config import CHAIN_IDS
        assert CHAIN_IDS["mumbai"] == 80001

    def test_goerli_resolves_correctly(self):
        """Deprecated but still present in some configs."""
        from subgraph_wizard.generate.ponder_config import CHAIN_IDS
        assert CHAIN_IDS["goerli"] == 5

    def test_unknown_slug_generates_id_zero(self):
        """Unknown slugs return 0 — caller handles that gracefully."""
        from subgraph_wizard.generate.ponder_config import CHAIN_IDS
        assert CHAIN_IDS.get("my-local-devnet", 0) == 0

    def test_mumbai_config_produces_correct_chain_id(self):
        """End-to-end: generating config for 'mumbai' must use id 80001."""
        cfg = _cfg(networks=[_net("mumbai", _contract_instances(_inst("0xABC", 0)))])
        out = render_ponder_config(cfg)
        assert "id: 80001" in out
        assert "PONDER_RPC_URL_80001" in out

    def test_goerli_config_produces_correct_chain_id(self):
        """End-to-end: 'goerli' must use id 5 (not 0)."""
        cfg = _cfg(networks=[_net("goerli", _contract_instances(_inst("0xABC", 0)))])
        out = render_ponder_config(cfg)
        assert "id: 5" in out
        assert "PONDER_RPC_URL_5" in out

    def test_blast_config_produces_correct_chain_id(self):
        """Newer L2: blast → 81457."""
        cfg = _cfg(networks=[_net("blast", _contract_instances(_inst("0xABC", 0)))])
        out = render_ponder_config(cfg)
        assert "id: 81457" in out

    def test_no_chain_id_zero_for_known_slugs(self):
        """None of the frontend slugs should produce id: 0 in the config."""
        for slug in self.FRONTEND_SLUGS:
            cfg = _cfg(networks=[_net(slug, _contract_instances(_inst("0xABC", 0)))])
            out = render_ponder_config(cfg)
            assert "id: 0" not in out, f"Slug '{slug}' produced id: 0"


# ── Mixed startBlock behaviour ────────────────────────────────────────────────

class TestMixedStartBlock:
    """
    When multiple instances of the same contract on the same chain have
    mixed startBlock values (some 0, some positive), the contract must
    start from 0 (i.e. no startBlock emitted) — not from the positive
    value.  Emitting the positive value would silently miss all events
    before that block for the zero-start instance.
    """

    def test_all_zero_startblock_omits_field(self):
        """When all instances have startBlock=0, no startBlock should be emitted."""
        cfg = _cfg(networks=[_net("mainnet", _contract_instances(
            _inst("0xAAA", 0),
            _inst("0xBBB", 0),
        ))])
        out = render_ponder_config(cfg)
        assert "startBlock" not in out

    def test_all_set_startblock_emits_minimum(self):
        """When all instances have a non-zero startBlock, emit the minimum."""
        cfg = _cfg(networks=[_net("mainnet", _contract_instances(
            _inst("0xAAA", 500_000),
            _inst("0xBBB", 200_000),
        ))])
        out = render_ponder_config(cfg)
        assert "startBlock: 200000" in out

    def test_mixed_zero_and_positive_omits_startblock(self):
        """
        If one instance has startBlock=0 (genesis) and another has a
        positive startBlock, the effective start is genesis → no
        startBlock emitted (wrong before: emitted the positive value).
        """
        cfg = _cfg(networks=[_net("mainnet", _contract_instances(
            _inst("0xAAA", 0),           # needs data from genesis
            _inst("0xBBB", 14_000_000),  # only needs recent data
        ))])
        out = render_ponder_config(cfg)
        # Must NOT emit the positive value — that would miss the genesis instance
        assert "startBlock: 14000000" not in out
        assert "startBlock" not in out

    def test_single_instance_positive_startblock_emitted(self):
        """Single instance with a positive startBlock should still be emitted."""
        cfg = _cfg(networks=[_net("mainnet", _contract_instances(
            _inst("0xAAA", 14_265_505),
        ))])
        out = render_ponder_config(cfg)
        assert "startBlock: 14265505" in out

    def test_single_instance_zero_startblock_omitted(self):
        """Single instance with startBlock=0 should not emit startBlock."""
        cfg = _cfg(networks=[_net("mainnet", _contract_instances(
            _inst("0xAAA", 0),
        ))])
        out = render_ponder_config(cfg)
        assert "startBlock" not in out



# ── Stale contract filtering ───────────────────────────────────────────────────

class TestStaleContractFiltering:
    """render_ponder_config must not import ABIs for contracts that are in the
    networks config but have been deleted from the canvas (no matching node).

    Without this guard the generated ponder.config.ts would import a file that
    was never written, causing Ponder to crash with "Failed to load url ./abis/...".
    """

    # Helper: node with a real (non-empty) ABI so the import guard lets it through
    _ABI_ITEM = [{"type": "event", "name": "Transfer", "inputs": []}]

    def _node_with_abi(self, name):
        return {
            "id": f"cn-{name}",
            "type": "contract",
            "position": {},
            "data": {
                "name": name,
                "abi": self._ABI_ITEM,
                "events": [],
                "readFunctions": [],
            },
        }

    def test_deleted_contract_not_imported(self):
        """Contract in networks_config but not in nodes → no import emitted."""
        cfg = _cfg(
            networks=[_net("mainnet", {"OldContract": {"instances": [_inst("0xDEAD")]},
                                       "Token": {"instances": [_inst("0xBEEF")]}})],
            nodes=[self._node_with_abi("Token")],   # OldContract deleted from canvas
        )
        out = render_ponder_config(cfg)
        assert "OldContractAbi" not in out
        assert "OldContract" not in out

    def test_active_contract_still_imported(self):
        """Contract still on canvas with ABI data → import is present as normal."""
        cfg = _cfg(
            networks=[_net("mainnet", {"Token": {"instances": [_inst("0xBEEF")]}})],
            nodes=[self._node_with_abi("Token")],
        )
        out = render_ponder_config(cfg)
        assert 'import { TokenAbi } from "./abis/TokenAbi"' in out

    def test_contract_without_abi_data_not_imported(self):
        """Node exists but has no ABI data → import line is omitted.

        Note: the contract may still appear in the ``contracts:`` block (the
        validator warns about missing ABIs separately).  We only verify that no
        ``import`` statement is emitted — importing a missing file would crash
        Ponder at startup.
        """
        node_no_abi = {
            "id": "cn-Empty",
            "type": "contract",
            "position": {},
            "data": {"name": "Empty", "events": [], "readFunctions": []},
            # intentionally no "abi" key
        }
        cfg = _cfg(
            networks=[_net("mainnet", {"Empty": {"instances": [_inst("0xABC")]}})],
            nodes=[node_no_abi],
        )
        out = render_ponder_config(cfg)
        # The import line must not be emitted (that would crash Ponder)
        assert 'import { EmptyAbi }' not in out

    def test_deleted_contract_not_in_contracts_block(self):
        """Deleted contract must not appear in the contracts: {} block either."""
        cfg = _cfg(
            networks=[_net("mainnet", {"Ghost": {"instances": [_inst("0x111")]},
                                       "Real": {"instances": [_inst("0x222")]}})],
            nodes=[self._node_with_abi("Real")],
        )
        out = render_ponder_config(cfg)
        # Ghost must not appear anywhere in the config
        assert "Ghost" not in out
        # Real should appear in the contracts block
        assert "Real:" in out

    def test_deleted_contract_not_included_when_other_nodes_exist(self):
        """When some canvas contract nodes exist, contracts NOT in that set are
        filtered out, even if they appear in networks_config.

        This covers the real-world scenario: user has two contracts, deletes one,
        regenerates.  The surviving contract's canvas node is present, so the
        filter is active and the deleted contract is excluded.
        """
        cfg = _cfg(
            networks=[_net("mainnet", {
                "Survivor": {"instances": [_inst("0x111")]},
                "Deleted": {"instances": [_inst("0x222")]},
            })],
            nodes=[self._node_with_abi("Survivor")],  # only Survivor on canvas
        )
        out = render_ponder_config(cfg)
        assert "Deleted" not in out
        assert "DeletedAbi" not in out
        assert "Survivor:" in out

    def test_canvas_only_contract_still_included(self):
        """Contract with a canvas node (with ABI) but NO networks entry → still
        emitted (second-pass behaviour — we don't break existing functionality)."""
        cfg = _cfg(
            networks=[],   # no networks panel data at all
            nodes=[self._node_with_abi("Lone")],
        )
        out = render_ponder_config(cfg)
        # The contract should appear in the contracts block (with placeholder address)
        assert "Lone:" in out
        assert 'import { LoneAbi } from "./abis/LoneAbi"' in out


# ── Auto chain column in schema ────────────────────────────────────────────────

class TestAutoChainColumn:
    """render_ponder_schema must inject a `chain` column into every entity table."""

    def _cfg(self, nodes, edges=None):
        return {"nodes": nodes, "edges": edges or []}

    def _entity(self, node_id, name, fields=None):
        return {
            "id": node_id,
            "type": "entity",
            "position": {},
            "data": {"name": name, "fields": fields or [{"name": "id", "type": "ID", "required": True}]},
        }

    def test_chain_column_added_to_entity(self):
        from subgraph_wizard.generate.ponder_schema import render_ponder_schema
        cfg = self._cfg([self._entity("e1", "Transfer")])
        schema = render_ponder_schema(cfg)
        assert "chain: t.text().notNull()," in schema

    def test_chain_column_is_after_id(self):
        from subgraph_wizard.generate.ponder_schema import render_ponder_schema
        cfg = self._cfg([self._entity("e1", "Transfer")])
        schema = render_ponder_schema(cfg)
        id_pos = schema.index("id: t.text().primaryKey()")
        chain_pos = schema.index("chain: t.text().notNull(),")
        assert chain_pos > id_pos

    def test_chain_column_not_duplicated_when_user_has_chain(self):
        from subgraph_wizard.generate.ponder_schema import render_ponder_schema
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "chain", "type": "String"},
        ]
        cfg = self._cfg([self._entity("e1", "Transfer", fields=fields)])
        schema = render_ponder_schema(cfg)
        # Only one chain column entry
        assert schema.count("chain:") == 1

    def test_chain_column_added_to_all_entities(self):
        from subgraph_wizard.generate.ponder_schema import render_ponder_schema
        cfg = self._cfg([
            self._entity("e1", "Transfer"),
            self._entity("e2", "Approval"),
        ])
        schema = render_ponder_schema(cfg)
        assert schema.count("chain: t.text().notNull(),") == 2
