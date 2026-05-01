"""End-to-end integration tests for full Ponder project generation.

These tests exercise the complete pipeline from a visual-config.json dict
through all three generators (ponder_config, ponder_schema, ponder_compiler)
and verify the combined output, mimicking what _generate_ponder() in server.py
does when the user clicks Generate in Ponder mode.

No FastAPI test client is needed — we call the generators directly and inspect
the content of what would be written to disk.
"""

import json
import pytest

from subgraph_wizard.generate.ponder_config import (
    render_ponder_config,
    render_ponder_env_example,
    render_ponder_package_json,
    render_ponder_tsconfig,
    render_ponder_env_dts,
    render_ponder_howto,
)
from subgraph_wizard.generate.ponder_schema import render_ponder_schema
from subgraph_wizard.generate.ponder_compiler import compile_ponder, render_abi_ts

# ── Shared ABI fixtures ───────────────────────────────────────────────────────

ERC20_ABI = [
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
        "type": "event",
        "name": "Approval",
        "inputs": [
            {"name": "owner", "type": "address", "indexed": True},
            {"name": "spender", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "function",
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

# ── Config builder helpers ────────────────────────────────────────────────────

def _node(node_id, node_type, data):
    return {"id": node_id, "type": node_type, "position": {"x": 0, "y": 0}, "data": data}


def _contract_node(node_id, name, events=None, read_fns=None, abi=None, **flags):
    data = {
        "name": name,
        "abi": abi or [],
        "events": events or [],
        "readFunctions": read_fns or [],
    }
    data.update(flags)
    return _node(node_id, "contract", data)


def _entity_node(node_id, name, fields):
    return _node(node_id, "entity", {"name": name, "fields": fields})


def _agg_node(node_id, name, fields, trigger_events=None):
    return _node(node_id, "aggregateentity", {
        "name": name,
        "fields": fields,
        "triggerEvents": trigger_events or [],
    })


def _edge(eid, src, src_handle, tgt, tgt_handle):
    return {"id": eid, "source": src, "sourceHandle": src_handle,
            "target": tgt, "targetHandle": tgt_handle, "animated": False}


def _field(name, ftype, required=False):
    return {"name": name, "type": ftype, "required": required}


def _net_entry(network, contract_name, address, start_block=0, end_block=None, **chain_opts):
    inst = {"label": "main", "address": address, "startBlock": start_block}
    if end_block:
        inst["endBlock"] = end_block
    entry = {"network": network, "contracts": {contract_name: {"instances": [inst]}}}
    entry.update(chain_opts)
    return entry


def _full_cfg(nodes, edges, networks=None, ponder_settings=None, name="my-erc20"):
    return {
        "schema_version": 1,
        "subgraph_name": name,
        "output_mode": "ponder",
        "networks": networks or [],
        "nodes": nodes,
        "edges": edges,
        "ponder_settings": ponder_settings or {},
    }


# ── Helpers that run the full pipeline and return all outputs ─────────────────

def _generate(cfg) -> dict[str, str]:
    """Run the full Ponder generation pipeline, return {filename: content}."""
    from subgraph_wizard.generate.ponder_config import render_ponder_api_index
    outputs = {}
    outputs["ponder.config.ts"] = render_ponder_config(cfg)
    outputs["ponder.schema.ts"] = render_ponder_schema(cfg)
    outputs["ponder-env.d.ts"] = render_ponder_env_dts()
    outputs["tsconfig.json"] = render_ponder_tsconfig()
    outputs["package.json"] = render_ponder_package_json(cfg.get("subgraph_name", ""))
    outputs[".env.example"] = render_ponder_env_example(cfg)
    outputs["src/api/index.ts"] = render_ponder_api_index()
    outputs["PONDER_HOWTO.md"] = render_ponder_howto(cfg.get("subgraph_name", ""), "/out", cfg)
    outputs.update(compile_ponder(cfg))  # adds src/index.ts
    for node in cfg.get("nodes", []):
        if node.get("type") == "contract":
            name = node["data"].get("name", "")
            abi = node["data"].get("abi")
            if name and abi:
                outputs[f"abis/{name}Abi.ts"] = render_abi_ts(name, abi)
    return outputs


# ── Test 1: Simple ERC-20 Transfer → entity insert ───────────────────────────

class TestSimpleERC20Transfer:
    """Transfer event → TransferEvent entity. Wires from, to, value, timestamp."""

    @pytest.fixture
    def cfg(self):
        fields = [
            _field("id", "ID", required=True),
            _field("from", "String"),
            _field("to", "String"),
            _field("value", "BigInt"),
            _field("timestamp", "BigInt"),
        ]
        nodes = [
            _contract_node("c1", "ERC20",
                events=[{"name": "Transfer", "params": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                ]}],
                abi=ERC20_ABI,
            ),
            _entity_node("e1", "TransferEvent", fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "event-Transfer-from", "e1", "field-from"),
            _edge("ed3", "c1", "event-Transfer-to", "e1", "field-to"),
            _edge("ed4", "c1", "event-Transfer-value", "e1", "field-value"),
            _edge("ed5", "c1", "implicit-block-timestamp", "e1", "field-timestamp"),
        ]
        return _full_cfg(nodes, edges,
            networks=[_net_entry("mainnet", "ERC20", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 8928158)],
        )

    @pytest.fixture
    def outputs(self, cfg):
        return _generate(cfg)

    # ponder.config.ts
    def test_config_has_mainnet_chain(self, outputs):
        assert "mainnet:" in outputs["ponder.config.ts"]
        assert "id: 1," in outputs["ponder.config.ts"]

    def test_config_has_erc20_contract(self, outputs):
        assert "ERC20:" in outputs["ponder.config.ts"]
        assert "ERC20Abi" in outputs["ponder.config.ts"]

    def test_config_has_start_block(self, outputs):
        assert "startBlock: 8928158" in outputs["ponder.config.ts"]

    def test_config_has_rpc_env_var(self, outputs):
        assert "PONDER_RPC_URL_1" in outputs["ponder.config.ts"]

    def test_config_no_database_block_for_pglite(self, outputs):
        assert "database:" not in outputs["ponder.config.ts"]

    def test_config_no_ordering_for_default(self, outputs):
        assert "ordering:" not in outputs["ponder.config.ts"]

    # ponder.schema.ts
    def test_schema_has_transfer_event_table(self, outputs):
        assert "export const transferEvent = onchainTable" in outputs["ponder.schema.ts"]

    def test_schema_has_correct_field_types(self, outputs):
        schema = outputs["ponder.schema.ts"]
        assert "id: t.text().primaryKey()" in schema
        assert "value: t.bigint()" in schema

    # src/index.ts
    def test_handler_emitted(self, outputs):
        assert 'ponder.on("ERC20:Transfer"' in outputs["src/index.ts"]

    def test_handler_has_correct_signature(self, outputs):
        assert "async ({ event, context })" in outputs["src/index.ts"]

    def test_handler_inserts_entity(self, outputs):
        src = outputs["src/index.ts"]
        assert "context.db.insert(transferEvent)" in src

    def test_handler_maps_event_params(self, outputs):
        src = outputs["src/index.ts"]
        assert "event.args.from" in src
        assert "event.args.to" in src
        assert "event.args.value" in src

    def test_handler_maps_timestamp(self, outputs):
        assert "Number(event.block.timestamp)" in outputs["src/index.ts"]

    def test_handler_uses_event_id_for_entity_id(self, outputs):
        # Suffix-retry loop: raw id expr goes into __baseId; values() uses __id
        assert "__baseId = event.id" in outputs["src/index.ts"]
        assert "id: __id," in outputs["src/index.ts"]

    # ABI file
    def test_abi_ts_file_generated(self, outputs):
        assert "abis/ERC20Abi.ts" in outputs

    def test_abi_ts_exports_const(self, outputs):
        assert "export const ERC20Abi" in outputs["abis/ERC20Abi.ts"]
        assert "as const" in outputs["abis/ERC20Abi.ts"]

    def test_abi_ts_contains_transfer_event(self, outputs):
        assert "Transfer" in outputs["abis/ERC20Abi.ts"]

    # Package files
    def test_package_json_has_ponder_dep(self, outputs):
        pkg = json.loads(outputs["package.json"])
        assert "ponder" in pkg["dependencies"]

    def test_env_dts_has_reference(self, outputs):
        assert "ponder/env" in outputs["ponder-env.d.ts"]

    def test_tsconfig_is_valid_json(self, outputs):
        cfg = json.loads(outputs["tsconfig.json"])
        assert "compilerOptions" in cfg

    def test_env_example_has_rpc_var(self, outputs):
        assert "PONDER_RPC_URL_1" in outputs[".env.example"]

    def test_howto_md_has_project_name(self, outputs):
        assert "my-erc20" in outputs["PONDER_HOWTO.md"]

    def test_howto_md_has_rpc_var_name(self, outputs):
        """The specific RPC env var for the configured chain should be called out."""
        assert "PONDER_RPC_URL_1" in outputs["PONDER_HOWTO.md"]

    def test_howto_md_no_postgres_required_note(self, outputs):
        """PGlite config should NOT say 'PostgreSQL required'."""
        assert "PostgreSQL required" not in outputs["PONDER_HOWTO.md"]

    def test_howto_md_pglite_zero_config_note(self, outputs):
        """PGlite config should mention zero-config embedded database."""
        howto = outputs["PONDER_HOWTO.md"]
        assert "PGlite" in howto or "embedded" in howto

    def test_howto_uses_env_local_not_env(self, outputs):
        """HOWTO must instruct users to use .env.local (Ponder's convention)."""
        howto = outputs["PONDER_HOWTO.md"]
        assert ".env.local" in howto
        # Must NOT tell users to create a plain .env file
        assert "cp .env.example .env\n" not in howto
        assert "cp .env.example .env`" not in howto

    def test_api_index_ts_is_generated(self, outputs):
        """src/api/index.ts must be present — Ponder requires it as the API entry point."""
        assert "src/api/index.ts" in outputs

    def test_api_index_ts_exports_hono_app(self, outputs):
        """src/api/index.ts must export a Hono app."""
        api = outputs["src/api/index.ts"]
        assert "hono" in api.lower() or "Hono" in api
        assert "export default" in api

    def test_api_index_ts_is_valid_typescript(self, outputs):
        """src/api/index.ts must import from 'hono' and export a default."""
        api = outputs["src/api/index.ts"]
        assert 'from "hono"' in api or "from 'hono'" in api
        assert "export default" in api


# ── Test 2: Aggregate entity (running total with math) ───────────────────────

class TestAggregateRunningTotal:
    """Transfer event → AggregateEntity Counter with running total via Math node."""

    @pytest.fixture
    def cfg(self):
        agg_fields = [
            _field("id", "ID", required=True),
            _field("totalVolume", "BigInt"),
        ]
        nodes = [
            _contract_node("c1", "ERC20",
                events=[{"name": "Transfer", "params": [
                    {"name": "value", "type": "uint256"},
                ]}],
            ),
            _agg_node("a1", "VolumeCounter", agg_fields,
                trigger_events=[{"contractId": "c1", "eventName": "Transfer"}],
            ),
            {
                "id": "m1", "type": "math", "position": {"x": 200, "y": 0},
                "data": {"operation": "add"},
            },
        ]
        edges = [
            # Math node: left=prev totalVolume, right=event value → result
            _edge("ed1", "a1", "field-prev-totalVolume", "m1", "left"),
            _edge("ed2", "c1", "event-Transfer-value", "m1", "right"),
            # Math result → aggregate field-in-totalVolume
            _edge("ed3", "m1", "result", "a1", "field-in-totalVolume"),
        ]
        return _full_cfg(nodes, edges)

    def test_aggregate_handler_emitted(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        assert 'ponder.on("ERC20:Transfer"' in src

    def test_aggregate_uses_on_conflict(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        assert "onConflictDoUpdate" in src

    def test_aggregate_schema_emitted(self, cfg):
        schema = render_ponder_schema(cfg)
        assert "export const volumeCounter = onchainTable" in schema
        assert "totalVolume: t.bigint()" in schema

    def test_math_add_operator_in_handler(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        assert " + " in src


# ── Test 3: Setup handler + regular event side-by-side ───────────────────────

class TestSetupAndRegularEvent:
    """Contract has both Transfer event handler and a setup handler."""

    @pytest.fixture
    def cfg(self):
        transfer_fields = [_field("id", "ID", required=True)]
        global_fields = [
            _field("id", "ID", required=True),
            _field("count", "BigInt"),
        ]
        nodes = [
            _contract_node("c1", "ERC20",
                events=[{"name": "Transfer", "params": []}],
                hasSetupHandler=True,
            ),
            _entity_node("e1", "TransferEvent", transfer_fields),
            _entity_node("e2", "GlobalState", global_fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "event-setup", "e2", "trigger"),
        ]
        return _full_cfg(nodes, edges)

    def test_transfer_handler_emitted(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        assert 'ponder.on("ERC20:Transfer"' in src

    def test_setup_handler_emitted(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        assert 'ponder.on("ERC20:setup"' in src

    def test_setup_handler_uses_context_only_signature(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        setup_idx = src.index('ponder.on("ERC20:setup"')
        setup_block = src[setup_idx: setup_idx + 200]
        assert "async ({ context })" in setup_block
        assert "{ event, context }" not in setup_block

    def test_setup_entity_id_is_initial(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        # Suffix-retry loop: base id goes into __baseId
        assert '__baseId = "initial"' in src

    def test_transfer_entity_id_is_event_id(self, cfg):
        src = compile_ponder(cfg)["src/index.ts"]
        # Suffix-retry loop: raw id expr goes into __baseId
        assert "__baseId = event.id" in src

    def test_both_entities_in_schema(self, cfg):
        schema = render_ponder_schema(cfg)
        assert "export const transferEvent" in schema
        assert "export const globalState" in schema


# ── Test 4: Postgres + multichain + per-contract flags ───────────────────────

class TestAdvancedPonderSettings:
    """All advanced Ponder options enabled together."""

    @pytest.fixture
    def cfg(self):
        nodes = [
            _contract_node("c1", "ERC20",
                events=[{"name": "Transfer", "params": []}],
                includeCallTraces=True,
                includeTransactionReceipts=True,
            ),
        ]
        networks = [
            _net_entry("mainnet", "ERC20", "0xAAA", start_block=14_000_000,
                       end_block=15_000_000, pollingInterval=2000, ethGetLogsBlockRange=500),
        ]
        return _full_cfg(nodes, [], networks=networks,
                         ponder_settings={"database": "postgres", "ordering": "omnichain"})

    def test_postgres_database_block(self, cfg):
        config = render_ponder_config(cfg)
        assert 'kind: "postgres"' in config
        assert "DATABASE_URL" in config

    def test_omnichain_ordering(self, cfg):
        """omnichain is non-default so it must be explicitly emitted."""
        config = render_ponder_config(cfg)
        assert 'ordering: "omnichain"' in config

    def test_polling_interval(self, cfg):
        config = render_ponder_config(cfg)
        assert "pollingInterval: 2000" in config

    def test_eth_get_logs_block_range(self, cfg):
        """Correct Ponder option name is ethGetLogsBlockRange, not maxBlockRange."""
        config = render_ponder_config(cfg)
        assert "ethGetLogsBlockRange: 500" in config

    def test_end_block(self, cfg):
        config = render_ponder_config(cfg)
        assert "endBlock: 15000000" in config

    def test_include_call_traces(self, cfg):
        config = render_ponder_config(cfg)
        assert "includeCallTraces: true" in config

    def test_include_tx_receipts(self, cfg):
        config = render_ponder_config(cfg)
        assert "includeTransactionReceipts: true" in config

    def test_howto_postgres_required_note(self, cfg):
        """Postgres config must prominently note DATABASE_URL is required."""
        howto = render_ponder_howto(cfg["subgraph_name"], "/out", cfg)
        assert "PostgreSQL required" in howto or "DATABASE_URL" in howto

    def test_howto_omnichain_ordering_note(self, cfg):
        """omnichain ordering should produce a callout in the howto."""
        howto = render_ponder_howto(cfg["subgraph_name"], "/out", cfg)
        assert "omnichain" in howto

    def test_howto_rpc_var_in_troubleshooting(self, cfg):
        """The specific RPC env var must appear in the troubleshooting section."""
        howto = render_ponder_howto(cfg["subgraph_name"], "/out", cfg)
        assert "PONDER_RPC_URL_1" in howto


# ── Test 5: Multi-network, same contract on different chains ──────────────────

class TestMultiNetworkSameContract:
    """Token deployed on mainnet AND optimism — should appear on both chains."""

    @pytest.fixture
    def cfg(self):
        nodes = [
            _contract_node("c1", "Token",
                events=[{"name": "Transfer", "params": []}],
            ),
        ]
        networks = [
            _net_entry("mainnet", "Token", "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", 14_000_000),
            _net_entry("optimism", "Token", "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", 1_000_000),
        ]
        return _full_cfg(nodes, [], networks=networks)

    def test_both_chains_in_config(self, cfg):
        config = render_ponder_config(cfg)
        assert "mainnet:" in config
        assert "optimism:" in config

    def test_both_chain_ids_present(self, cfg):
        config = render_ponder_config(cfg)
        assert "id: 1," in config    # mainnet
        assert "id: 10," in config   # optimism

    def test_both_rpc_vars(self, cfg):
        config = render_ponder_config(cfg)
        assert "PONDER_RPC_URL_1" in config
        assert "PONDER_RPC_URL_10" in config

    def test_token_contract_in_config(self, cfg):
        config = render_ponder_config(cfg)
        assert "Token:" in config
        assert "TokenAbi" in config

    def test_multi_chain_object_format(self, cfg):
        """Contract on two chains uses the object chain: { mainnet: {...}, optimism: {...} } format."""
        config = render_ponder_config(cfg)
        assert "chain: {" in config
        assert "0xAAAA" in config
        assert "0xBBBB" in config

    def test_env_example_has_both_rpc_vars(self, cfg):
        env = render_ponder_env_example(cfg)
        assert "PONDER_RPC_URL_1=" in env
        assert "PONDER_RPC_URL_10=" in env


# ── Test 6: Contract with no network entry (second-pass fallback) ─────────────

class TestOrphanContract:
    """A contract node with no Networks panel entry falls back to first network."""

    @pytest.fixture
    def cfg(self):
        nodes = [
            _contract_node("c1", "Orphan",
                events=[{"name": "Transfer", "params": []}],
            ),
        ]
        # Only mainnet configured in networks, but no entry for "Orphan"
        networks = [_net_entry("mainnet", "OtherContract", "0xCCC")]
        return _full_cfg(nodes, [], networks=networks)

    def test_orphan_contract_still_in_config(self, cfg):
        config = render_ponder_config(cfg)
        assert "Orphan:" in config

    def test_orphan_uses_null_address(self, cfg):
        config = render_ponder_config(cfg)
        assert "0x0000000000000000000000000000000000000000" in config

    def test_orphan_abi_imported(self, cfg):
        config = render_ponder_config(cfg)
        assert "OrphanAbi" in config
