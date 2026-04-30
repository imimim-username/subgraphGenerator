"""Tests for generate/ponder_compiler.py — PonderCompiler and compile_ponder."""

import pytest
from subgraph_wizard.generate.ponder_compiler import compile_ponder, PonderCompiler

# ── Config builder helpers ─────────────────────────────────────────────────────

def _cfg(nodes=None, edges=None, networks=None):
    return {
        "schema_version": 1,
        "subgraph_name": "test",
        "networks": networks or [],
        "nodes": nodes or [],
        "edges": edges or [],
        "ponder_settings": {},
    }


def _contract(node_id, name, events=None, read_fns=None, **extra_data):
    data = {
        "name": name,
        "abi": [],
        "events": events or [],
        "readFunctions": read_fns or [],
    }
    data.update(extra_data)
    return {
        "id": node_id,
        "type": "contract",
        "position": {"x": 0, "y": 0},
        "data": data,
    }


def _event(name, params=None):
    return {"name": name, "params": params or []}


def _entity(node_id, name, fields=None):
    return {
        "id": node_id,
        "type": "entity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
        },
    }


def _agg_entity(node_id, name, fields=None):
    return {
        "id": node_id,
        "type": "aggregateentity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [
                {"name": "id", "type": "ID", "required": True},
                {"name": "count", "type": "BigInt"},
            ],
            "triggerEvents": [],
        },
    }


def _edge(eid, source, source_handle, target, target_handle):
    return {
        "id": eid,
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": target_handle,
        "animated": False,
    }


def _read_fn(name, inputs=None, outputs=None):
    return {
        "name": name,
        "inputs": inputs or [],
        "outputs": outputs or [{"name": "result", "type": "uint256"}],
    }


# ── Output file structure ─────────────────────────────────────────────────────

class TestOutputStructure:
    def test_returns_dict_with_src_index_ts(self):
        result = compile_ponder(_cfg())
        assert "src/index.ts" in result

    def test_always_imports_ponder_registry(self):
        result = compile_ponder(_cfg())
        assert 'import { ponder } from "ponder:registry"' in result["src/index.ts"]

    def test_no_handler_for_unwired_event(self):
        """Events with no downstream entity nodes should produce no handler."""
        nodes = [_contract("c1", "Token", events=[_event("Transfer")])]
        result = compile_ponder(_cfg(nodes=nodes))
        assert "ponder.on" not in result["src/index.ts"]

    def test_handler_emitted_for_wired_event(self):
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer", [{"name": "from", "type": "address"}])]),
            _entity("e1", "Transfer"),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        result = compile_ponder(_cfg(nodes=nodes, edges=edges))
        src = result["src/index.ts"]
        assert 'ponder.on("Token:Transfer"' in src
        assert "async ({ event, context })" in src

    def test_schema_import_added_when_entities_used(self):
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Transfer"),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        result = compile_ponder(_cfg(nodes=nodes, edges=edges))
        assert 'from "ponder:schema"' in result["src/index.ts"]


# ── Entity insert generation ───────────────────────────────────────────────────

class TestEntityInsert:
    def test_insert_statement_emitted(self):
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Transfer"),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "context.db.insert" in src
        assert "transfer" in src  # schema var name (camelCase)

    def test_default_id_is_event_id(self):
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Transfer"),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "id: event.id" in src

    def test_event_param_wired_to_field(self):
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "from", "type": "String"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer", [{"name": "from", "type": "address"}])]),
            _entity("e1", "Transfer", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "event-Transfer-from", "e1", "field-from"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.args.from" in src

    def test_implicit_block_timestamp(self):
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "ts", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Transfer", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-block-timestamp", "e1", "field-ts"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "Number(event.block.timestamp)" in src

    def test_implicit_tx_hash(self):
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "txHash", "type": "String"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Transfer", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-tx-hash", "e1", "field-txHash"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.transaction.hash" in src


# ── Setup handler ─────────────────────────────────────────────────────────────

class TestSetupHandler:
    def test_setup_handler_emitted_when_flag_set(self):
        nodes = [_contract("c1", "Token", hasSetupHandler=True)]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        assert 'ponder.on("Token:setup"' in src

    def test_setup_handler_not_emitted_when_flag_absent(self):
        nodes = [_contract("c1", "Token")]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        assert "setup" not in src

    def test_setup_handler_not_emitted_when_flag_false(self):
        nodes = [_contract("c1", "Token", hasSetupHandler=False)]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        assert "setup" not in src

    def test_setup_handler_uses_context_only_signature(self):
        """Setup handler must NOT have `event` in its parameter destructuring."""
        nodes = [_contract("c1", "Token", hasSetupHandler=True)]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        assert "async ({ context })" in src
        # The setup handler itself should not destructure `event`
        setup_block_start = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_block_start:setup_block_start + 200]
        assert "{ event, context }" not in setup_block

    def test_setup_handler_stub_when_no_entities_wired(self):
        nodes = [_contract("c1", "Token", hasSetupHandler=True)]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        # Should produce a stub with a TODO
        assert "TODO" in src or "seed initial state" in src

    def test_setup_handler_entity_default_id_is_initial(self):
        """Entities wired to setup should default id to 'initial', not event.id."""
        nodes = [
            _contract("c1", "Token", hasSetupHandler=True),
            _entity("e1", "Global"),
        ]
        edges = [_edge("ed1", "c1", "event-setup", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert 'id: "initial"' in src
        assert "id: event.id" not in src

    def test_setup_and_regular_events_both_emitted(self):
        """Having both setup and a Transfer event should emit two handlers."""
        nodes = [
            _contract("c1", "Token",
                events=[_event("Transfer")],
                hasSetupHandler=True,
            ),
            _entity("e1", "Transfer"),
            _entity("e2", "Global"),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "event-setup", "e2", "trigger"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert 'ponder.on("Token:Transfer"' in src
        assert 'ponder.on("Token:setup"' in src

    def test_setup_transfer_handler_still_uses_event_id(self):
        """The Transfer handler should still use event.id, not 'initial'."""
        nodes = [
            _contract("c1", "Token",
                events=[_event("Transfer")],
                hasSetupHandler=True,
            ),
            _entity("e1", "Transfer"),
            _entity("e2", "Global"),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "event-setup", "e2", "trigger"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "id: event.id" in src   # Transfer handler
        assert 'id: "initial"' in src  # setup handler


# ── ContractRead node ─────────────────────────────────────────────────────────

class TestContractRead:
    def _make_contractread_config(self, event_name="Transfer", has_setup=False):
        read_fn = _read_fn("balanceOf", inputs=[{"name": "account", "type": "address"}])
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "balance", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token",
                events=[_event(event_name)] if event_name != "setup" else [],
                read_fns=[read_fn],
                hasSetupHandler=has_setup,
            ),
            {"id": "cr1", "type": "contractread", "position": {}, "data": {"contractNodeId": "c1", "fnIndex": 0}},
            _entity("e1", "Balance", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", f"event-{event_name}", "e1", "trigger"),
            _edge("ed2", "cr1", "out-result", "e1", "field-balance"),
        ]
        return nodes, edges

    def test_contractread_in_event_handler_includes_blocknumber(self):
        nodes, edges = self._make_contractread_config(event_name="Transfer")
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.block.number" in src
        assert "readContract" in src

    def test_contractread_in_setup_handler_omits_blocknumber(self):
        """Critical: setup handlers have no event, so blockNumber must be omitted."""
        read_fn = _read_fn("totalSupply")
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "supply", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", read_fns=[read_fn], hasSetupHandler=True),
            {"id": "cr1", "type": "contractread", "position": {}, "data": {"contractNodeId": "c1", "fnIndex": 0}},
            _entity("e1", "GlobalState", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-setup", "e1", "trigger"),
            _edge("ed2", "cr1", "out-result", "e1", "field-supply"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "readContract" in src
        # Must NOT reference event in the setup handler's readContract call
        setup_idx = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_idx:]
        assert "event.block.number" not in setup_block

    def test_contractread_abi_imported(self):
        nodes, edges = self._make_contractread_config(event_name="Transfer")
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "TokenAbi" in src

    def test_contractread_function_name_emitted(self):
        nodes, edges = self._make_contractread_config(event_name="Transfer")
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert 'functionName: "balanceOf"' in src


# ── Aggregate entity ───────────────────────────────────────────────────────────

class TestAggregateEntity:
    def test_aggregate_uses_onconflict(self):
        agg = _agg_entity("a1", "Counter", fields=[
            {"name": "id", "type": "ID", "required": True},
            {"name": "count", "type": "BigInt"},
        ])
        agg["data"]["triggerEvents"] = [{"contractId": "c1", "eventName": "Transfer"}]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            agg,
        ]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        assert "onConflictDoUpdate" in src or "onConflictDoNothing" in src


# ── Multiple contracts ─────────────────────────────────────────────────────────

class TestMultipleContracts:
    def test_multiple_contracts_emit_multiple_handlers(self):
        nodes = [
            _contract("c1", "TokenA", events=[_event("Transfer")]),
            _contract("c2", "TokenB", events=[_event("Approval")]),
            _entity("e1", "TransferEvent"),
            _entity("e2", "ApprovalEvent"),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c2", "event-Approval", "e2", "trigger"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert 'ponder.on("TokenA:Transfer"' in src
        assert 'ponder.on("TokenB:Approval"' in src

    def test_multiple_events_same_contract(self):
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer"), _event("Approval")]),
            _entity("e1", "TransferEvent"),
            _entity("e2", "ApprovalEvent"),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "event-Approval", "e2", "trigger"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert 'ponder.on("Token:Transfer"' in src
        assert 'ponder.on("Token:Approval"' in src

    def test_unnamed_contract_skipped(self):
        nodes = [_contract("c1", "")]  # name is empty
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        assert "ponder.on" not in src


# ── Implicit ports ────────────────────────────────────────────────────────────

class TestImplicitPorts:
    def test_implicit_address(self):
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "addr", "type": "String"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Ev", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-address", "e1", "field-addr"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.log.address" in src

    def test_implicit_block_number(self):
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "blk", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Ev", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-block-number", "e1", "field-blk"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.block.number" in src
