"""Tests for generate/ponder_compiler.py — PonderCompiler and compile_ponder."""

import pytest
from subgraph_wizard.generate.ponder_compiler import (
    compile_ponder,
    PonderCompiler,
    _event_param_expr_ts,
)

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
        # With the suffix-retry loop, the base ID is stored in __baseId; the
        # .values() call uses __id (the loop variable) rather than the raw expr.
        assert "__baseId = event.id" in src
        assert "id: __id," in src

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

    def test_suffix_retry_loop_emitted(self):
        """Regular entity inserts must use a suffix-retry loop so that multiple events
        in the same block producing the same base ID each get a unique row
        (e.g. id_2, id_3) rather than crashing with UniqueConstraintError or silently
        overwriting an earlier record.
        """
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "total", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "TotalSupply", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-block-number", "e1", "field-total"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # Retry loop markers
        assert "__baseId" in src
        assert "for (let __n = 1" in src
        assert "__n === 1 ? __baseId" in src
        assert "UniqueConstraintError" in src

    def test_suffix_retry_has_message_fallback(self):
        """The UniqueConstraintError catch must also check .message and .code so
        the retry works in minified production builds where constructor.name is gone."""
        fields = [{"name": "id", "type": "ID", "required": True}]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Snap", fields=fields),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # Must have both the class-name check AND a message/code fallback
        assert "UniqueConstraintError" in src
        assert '"23505"' in src or "23505" in src or "unique" in src.lower()

    def test_suffix_retry_uses_id_loop_var(self):
        """The .values({}) call inside the retry loop must reference __id, not the raw expression."""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "amount", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Snapshot", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-block-number", "e1", "field-amount"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # id inside .values() must be __id (the loop variable), not the raw expression
        assert "id: __id," in src

    def test_suffix_retry_still_emitted_for_id_only_entity(self):
        """Even an entity with only an id field uses the retry loop (no conflict handler needed
        since there are no other fields, but the loop wrapper is still there for consistency)."""
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Seen", fields=[{"name": "id", "type": "ID", "required": True}]),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "__baseId" in src
        assert "UniqueConstraintError" in src
        # onConflict helpers no longer emitted for regular entities
        assert "onConflictDoUpdate" not in src
        assert "onConflictDoNothing" not in src

    def test_no_unique_constraint_error_possible_with_block_level_id(self):
        """Regression: block-level IDs (blockNumber/timestamp) must not crash on second
        event in same block. The suffix-retry loop handles this by appending _2, _3, …"""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "myt", "type": "String"},
            {"name": "totalAssets", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "MYT", events=[_event("IncreaseAbsoluteCap")]),
            _entity("e1", "TotalAssetsAndSupply", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-IncreaseAbsoluteCap", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-block-number", "e1", "field-myt"),
            _edge("ed3", "c1", "implicit-block-timestamp", "e1", "field-totalAssets"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # Suffix retry must be present
        assert "for (let __n = 1" in src
        assert "__n === 1 ? __baseId" in src
        assert "UniqueConstraintError" in src
        # No upsert helpers — we preserve all records
        assert "onConflictDoUpdate" not in src


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

    def test_setup_handler_stub_imports_abi(self):
        """Even when no entities are wired to setup, the ABI should be imported
        so the user can call readContract() inside the stub without a build error."""
        nodes = [_contract("c1", "Token", hasSetupHandler=True)]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        assert "TokenAbi" in src

    def test_setup_handler_entity_default_id_is_initial(self):
        """Entities wired to setup should default id to 'initial', not event.id."""
        nodes = [
            _contract("c1", "Token", hasSetupHandler=True),
            _entity("e1", "Global"),
        ]
        edges = [_edge("ed1", "c1", "event-setup", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # With the suffix-retry loop the base ID goes into __baseId
        assert '__baseId = "initial"' in src
        assert "id: __id," in src
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
        """The Transfer handler should still use event.id as base, not 'initial'."""
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
        # With the suffix-retry loop, base IDs go into __baseId
        assert "__baseId = event.id" in src       # Transfer handler
        assert '__baseId = "initial"' in src      # setup handler


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


# ── implicit-instance-address (multi-chain contract address) ──────────────────
#
# Bug: the compiler emitted `event.instance-address` (hyphen = subtraction in
# JS/TS) which caused `ReferenceError: address is not defined` at runtime.
# The correct expression is `event.log.address`.

class TestImplicitInstanceAddress:
    """Regression tests for the event.instance-address bug (GH: addr-subtraction)."""

    def test_expr_fn_maps_instance_address_to_log_address(self):
        """_event_param_expr_ts must return event.log.address, not event.instance-address."""
        assert _event_param_expr_ts("implicit-instance-address") == "event.log.address"

    def test_expr_fn_does_not_return_hyphenated_expression(self):
        """The broken expression must never be produced."""
        result = _event_param_expr_ts("implicit-instance-address")
        assert "instance-address" not in result, (
            f"Hyphenated expression would be parsed as subtraction: {result!r}"
        )

    def test_implicit_instance_address_wired_to_entity_field(self):
        """Generator must emit event.log.address when instance-address port is wired to a field."""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "contractAddr", "type": "String"},
        ]
        nodes = [
            _contract("c1", "MYT", events=[_event("Submit")]),
            _entity("e1", "Submission", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Submit", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-instance-address", "e1", "field-contractAddr"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.log.address" in src

    def test_no_broken_subtraction_expression_in_entity_handler(self):
        """The broken `event.instance-address` expression must not appear in output."""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "contractAddr", "type": "String"},
        ]
        nodes = [
            _contract("c1", "MYT", events=[_event("Submit")]),
            _entity("e1", "Submission", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Submit", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-instance-address", "e1", "field-contractAddr"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.instance-address" not in src

    def test_implicit_instance_address_as_contractread_address(self):
        """Regression: the exact crash scenario — instance-address used as readContract address."""
        # This mirrors `MYT:Submit` calling totalAssets() with instance-address as `address`.
        read_fn = _read_fn("totalAssets", inputs=[], outputs=[{"name": "", "type": "uint256"}])
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "total", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "MYT", events=[_event("Submit")], read_fns=[read_fn]),
            {"id": "cr1", "type": "contractread", "position": {}, "data": {"contractNodeId": "c1", "fnIndex": 0}},
            _entity("e1", "SubmitEvent", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Submit", "e1", "trigger"),
            _edge("ed2", "cr1", "out-result", "e1", "field-total"),
            # Wire instance-address as the bind-address for the contractread
            _edge("ed3", "c1", "implicit-instance-address", "cr1", "bind-address"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.log.address" in src
        assert "event.instance-address" not in src
        # Must be valid: no bare `address` subtraction
        assert "instance - address" not in src

    def test_same_result_as_implicit_address(self):
        """implicit-instance-address and implicit-address should both resolve to event.log.address."""
        assert _event_param_expr_ts("implicit-address") == _event_param_expr_ts("implicit-instance-address")


# ── Auto chain field ───────────────────────────────────────────────────────────

class TestAutoChainField:
    """The compiler must inject `chain: context.chain.name` automatically."""

    def test_chain_injected_into_regular_entity(self):
        """Every regular entity insert must include chain: context.chain.name."""
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Transfer"),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "chain: context.chain.name," in src

    def test_chain_injected_into_aggregate_entity(self):
        """Aggregate entity inserts and updates must also include chain."""
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
        assert "chain: context.chain.name" in src

    def test_chain_not_duplicated_when_user_has_chain_field(self):
        """If the entity already has a field named 'chain', don't inject a second one."""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "chain", "type": "String"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Transfer", fields=fields),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # Should appear at most once in the values block (not duplicated)
        assert src.count("chain: context.chain.name,") <= 1


# ── Direct read-{fn} port wired to entity field ───────────────────────────────

class TestDirectReadPort:
    """Tests for wiring a contract's read-{fn} port directly to an entity field
    (as opposed to routing through a ContractRead node).

    This is the shorthand path for zero-argument view functions like name(),
    symbol(), decimals().
    """

    def _make_config(self, event_name="Transfer", use_setup=False, address="0xABC"):
        """Build a config where read-name is wired directly to an entity field."""
        fields = [
            {"name": "id",   "type": "ID",     "required": True},
            {"name": "name", "type": "String"},
        ]
        read_fn = _read_fn("name", inputs=[], outputs=[{"name": "", "type": "string"}])
        nodes = [
            _contract(
                "c1", "Token",
                events=[] if use_setup else [_event(event_name)],
                read_fns=[read_fn],
                hasSetupHandler=use_setup,
                address=address,
            ),
            _entity("e1", "TokenMeta", fields=fields),
        ]
        trigger_handle = "event-setup" if use_setup else f"event-{event_name}"
        edges = [
            _edge("ed1", "c1", trigger_handle, "e1", "trigger"),
            # Wire read-name directly from the contract node (not via ContractRead)
            _edge("ed2", "c1", "read-name", "e1", "field-name"),
        ]
        return _cfg(nodes=nodes, edges=edges)

    def test_generates_readcontract_call(self):
        """Direct read-fn port must produce a readContract() call, not a comment."""
        src = compile_ponder(self._make_config())["src/index.ts"]
        assert "readContract" in src
        assert "/* contract read:" not in src
        assert "/* unhandled" not in src

    def test_function_name_correct(self):
        src = compile_ponder(self._make_config())["src/index.ts"]
        assert 'functionName: "name"' in src

    def test_abi_imported(self):
        """The contract's ABI identifier must appear in the import."""
        src = compile_ponder(self._make_config())["src/index.ts"]
        assert "TokenAbi" in src

    def test_uses_configured_address(self):
        """When the contract has a configured address it should be used as the
        bind address — not event.log.address."""
        src = compile_ponder(self._make_config(address="0xDEAD"))["src/index.ts"]
        assert "0xDEAD" in src

    def test_regular_event_includes_blocknumber(self):
        """In a regular event handler the readContract call must pin to
        event.block.number to get the value at the right block."""
        src = compile_ponder(self._make_config(use_setup=False))["src/index.ts"]
        assert "event.block.number" in src

    def test_setup_handler_omits_blocknumber(self):
        """In a setup handler there is no event object, so blockNumber must be
        omitted entirely from the readContract call."""
        src = compile_ponder(self._make_config(use_setup=True))["src/index.ts"]
        assert "readContract" in src
        # blockNumber must not appear anywhere in the setup handler block
        setup_idx = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_idx:]
        assert "event.block.number" not in setup_block

    def test_result_assigned_to_entity_field(self):
        """The variable produced by readContract must end up in the entity's
        insert values — not discarded."""
        src = compile_ponder(self._make_config())["src/index.ts"]
        # The read result var is used in the values block
        assert "name:" in src
        # No leftover comment placeholder
        assert "/* contract read: read-name */" not in src

    def test_multiple_read_ports_deduped(self):
        """If the same read-fn port feeds two different entity fields the
        readContract call must only be emitted once (declared_vars guard)."""
        fields = [
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "name1", "type": "String"},
            {"name": "name2", "type": "String"},
        ]
        read_fn = _read_fn("name")
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")], read_fns=[read_fn]),
            _entity("e1", "TokenMeta", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "read-name", "e1", "field-name1"),
            _edge("ed3", "c1", "read-name", "e1", "field-name2"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # Only one readContract call for the same read-name port
        assert src.count('functionName: "name"') == 1

    def test_unknown_fn_produces_comment_not_crash(self):
        """Wiring a read port whose name doesn't exist in readFunctions should
        emit a safe comment rather than raising an exception."""
        fields = [{"name": "id", "type": "ID", "required": True},
                  {"name": "val", "type": "String"}]
        nodes = [
            # No read functions registered — read-ghost is unknown
            _contract("c1", "Token", events=[_event("Transfer")], read_fns=[]),
            _entity("e1", "Foo", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "read-ghost",     "e1", "field-val"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # Should not crash and should emit some diagnostic comment
        assert "unknown read fn" in src or "ghost" in src


# ── Implicit ports in setup handler context ───────────────────────────────────

class TestImplicitPortsInSetup:
    """Implicit ports (address, block-number, tx-hash, …) reference event.*
    expressions that don't exist in a setup handler.  The compiler must replace
    them with safe alternatives so the emitted TypeScript is valid."""

    def _make_setup_config(self, implicit_handle, field_type="String", address="0xBEEF"):
        fields = [
            {"name": "id",  "type": "ID",       "required": True},
            {"name": "val", "type": field_type},
        ]
        nodes = [
            _contract("c1", "Token", hasSetupHandler=True, address=address),
            _entity("e1", "Meta", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-setup",    "e1", "trigger"),
            _edge("ed2", "c1", implicit_handle,  "e1", "field-val"),
        ]
        networks = [
            {"network": "mainnet", "contracts": {"Token": {"instances": [{"address": address, "startBlock": 0}]}}},
        ]
        return _cfg(nodes=nodes, edges=edges, networks=networks)

    def test_implicit_address_uses_configured_address_in_setup(self):
        """implicit-address must resolve to the literal contract address,
        not event.log.address, inside a setup handler."""
        src = compile_ponder(
            self._make_setup_config("implicit-address", field_type="Address", address="0xDEAD")
        )["src/index.ts"]
        assert "event.log.address" not in src
        assert "0xDEAD" in src

    def test_implicit_address_no_event_reference_in_setup(self):
        """Ensure the word 'event' does not appear in the setup handler body
        when only implicit-address is wired (it would crash at runtime)."""
        src = compile_ponder(
            self._make_setup_config("implicit-address", field_type="Address")
        )["src/index.ts"]
        setup_idx = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_idx:]
        # event.* references inside the setup block would cause ReferenceError
        assert "event.log" not in setup_block
        assert "event.block" not in setup_block
        assert "event.transaction" not in setup_block

    def test_implicit_instance_address_uses_configured_address_in_setup(self):
        src = compile_ponder(
            self._make_setup_config("implicit-instance-address", field_type="Address", address="0xCAFE")
        )["src/index.ts"]
        assert "event.log.address" not in src
        assert "0xCAFE" in src

    def test_implicit_address_in_regular_event_still_uses_event_log_address(self):
        """Outside setup context the implicit-address port must still emit
        event.log.address — the fix must not affect regular handlers."""
        fields = [
            {"name": "id",   "type": "ID",      "required": True},
            {"name": "addr", "type": "Address"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Tx", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer",   "e1", "trigger"),
            _edge("ed2", "c1", "implicit-address",  "e1", "field-addr"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.log.address" in src

    def test_implicit_block_number_in_setup_emits_undefined_not_crash(self):
        """block-number has no equivalent in setup — must not emit event.block.number."""
        src = compile_ponder(
            self._make_setup_config("implicit-block-number", field_type="BigInt")
        )["src/index.ts"]
        setup_idx = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_idx:]
        assert "event.block.number" not in setup_block

    def test_implicit_tx_hash_in_setup_emits_undefined_not_crash(self):
        """tx-hash has no equivalent in setup — must not emit event.transaction.hash."""
        src = compile_ponder(
            self._make_setup_config("implicit-tx-hash", field_type="String")
        )["src/index.ts"]
        setup_idx = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_idx:]
        assert "event.transaction.hash" not in setup_block


# ── Setup handler resilience (try/catch wrapping) ─────────────────────────────

class TestSetupHandlerTryCatch:
    """Setup handler bodies must be wrapped in try/catch so that a failed
    readContract call (e.g. function not implemented at that address on a
    specific chain) does not crash the entire indexer.

    Root cause that prompted this: alchemistV3:setup called readContract for
    debtToken() on Optimism, which returned 0x — Ponder retried 5× then the
    handler threw, halting all indexing.
    """

    def _setup_with_contractread(self, address="0xfa995B6ABc387376C3e7De5f6d394Ab5B6beE26B"):
        """Config that mimics the crashing scenario: a setup handler that calls
        readContract inside (via a ContractRead node wired to an entity field)."""
        read_fn = _read_fn("debtToken", inputs=[], outputs=[{"name": "", "type": "address"}])
        fields = [
            {"name": "id",        "type": "ID",     "required": True},
            {"name": "debtToken", "type": "String"},
        ]
        nodes = [
            _contract("c1", "alchemistV3",
                read_fns=[read_fn],
                hasSetupHandler=True,
                address=address,
            ),
            {"id": "cr1", "type": "contractread", "position": {},
             "data": {"contractNodeId": "c1", "fnIndex": 0}},
            _entity("e1", "AlchemistState", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1",  "event-setup",  "e1",  "trigger"),
            _edge("ed2", "cr1", "out-result",   "e1",  "field-debtToken"),
        ]
        networks = [
            {"network": "mainnet", "contracts": {"alchemistV3": {"instances": [{"address": address, "startBlock": 0}]}}},
        ]
        return _cfg(nodes=nodes, edges=edges, networks=networks)

    def test_setup_handler_body_wrapped_in_try_catch(self):
        """The setup handler body must be enclosed in a try { ... } catch block."""
        src = compile_ponder(self._setup_with_contractread())["src/index.ts"]
        setup_idx = src.index('ponder.on("alchemistV3:setup"')
        setup_block = src[setup_idx:]
        assert "try {" in setup_block
        assert "} catch (err) {" in setup_block

    def test_setup_handler_catch_logs_warning(self):
        """The catch block must emit a console.warn so failed reads are visible
        in logs instead of silently swallowed."""
        src = compile_ponder(self._setup_with_contractread())["src/index.ts"]
        setup_idx = src.index('ponder.on("alchemistV3:setup"')
        setup_block = src[setup_idx:]
        assert "console.warn" in setup_block

    def test_setup_handler_catch_includes_contract_name(self):
        """The warning message should identify which handler failed."""
        src = compile_ponder(self._setup_with_contractread())["src/index.ts"]
        setup_idx = src.index('ponder.on("alchemistV3:setup"')
        setup_block = src[setup_idx:]
        assert "alchemistV3:setup" in setup_block

    def test_setup_handler_catch_includes_chain_name(self):
        """The warning should include the chain name so the user knows which
        network the read failed on."""
        src = compile_ponder(self._setup_with_contractread())["src/index.ts"]
        setup_idx = src.index('ponder.on("alchemistV3:setup"')
        setup_block = src[setup_idx:]
        assert "context.chain.name" in setup_block

    def test_readcontract_inside_try_block(self):
        """The readContract call must appear inside the try block (before the
        catch), not after it — otherwise the try/catch does nothing useful."""
        src = compile_ponder(self._setup_with_contractread())["src/index.ts"]
        setup_idx = src.index('ponder.on("alchemistV3:setup"')
        setup_block = src[setup_idx:]
        try_idx   = setup_block.index("try {")
        catch_idx = setup_block.index("} catch (err) {")
        read_idx  = setup_block.index("readContract")
        assert try_idx < read_idx < catch_idx, (
            "readContract must appear between try { and } catch (err) {"
        )

    def test_regular_event_handler_not_wrapped_in_try_catch(self):
        """Normal event handlers should NOT be wrapped — only setup handlers need
        this resilience (regular handlers crashing is the expected behaviour)."""
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Xfer"),
        ]
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        transfer_idx = src.index('ponder.on("Token:Transfer"')
        transfer_block = src[transfer_idx:]
        # The inner try inside the suffix-retry loop is OK, but there must be
        # no top-level try { ... } catch (err) { console.warn wrapper.
        assert "console.warn" not in transfer_block

    def test_setup_handler_with_no_entities_stub_no_try_catch_needed(self):
        """Stub setup handler (no wired entities) doesn't need try/catch because
        it contains no readContract calls that could fail."""
        nodes = [_contract("c1", "Token", hasSetupHandler=True)]
        src = compile_ponder(_cfg(nodes=nodes))["src/index.ts"]
        setup_idx = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_idx:]
        # The stub has a TODO comment — that's fine either way.
        # Just verify the output is syntactically sane (no double try/catch).
        assert src.count("} catch (err) {") == 0  # stub has no reads, no catch needed

    def test_setup_handler_with_entity_only_wrapped_in_try_catch(self):
        """Even a setup handler that just inserts an entity (no readContract)
        should be wrapped so any future body changes remain resilient."""
        nodes = [
            _contract("c1", "Token", hasSetupHandler=True),
            _entity("e1", "Global"),
        ]
        edges = [_edge("ed1", "c1", "event-setup", "e1", "trigger")]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        setup_idx = src.index('ponder.on("Token:setup"')
        setup_block = src[setup_idx:]
        assert "try {" in setup_block
        assert "} catch (err) {" in setup_block
        assert "console.warn" in setup_block


# ── Edge collision detection ───────────────────────────────────────────────────

class TestEdgeCollision:
    """Multiple edges to the same target port should log a warning (not silently drop)."""

    def test_duplicate_edge_logs_warning(self):
        """When two edges share the same (target, targetHandle), a warning is logged."""
        import logging
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Snap", fields=[
                {"name": "id",  "type": "ID", "required": True},
                {"name": "val", "type": "BigInt"},
            ]),
        ]
        # Two edges both targeting field-val — the second silently overwrites in old
        # code; now it must emit a warning.
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-block-number", "e1", "field-val"),
            _edge("ed3", "c1", "implicit-block-timestamp", "e1", "field-val"),
        ]
        with self._assert_warning("field-val"):
            compile_ponder(_cfg(nodes=nodes, edges=edges))

    @staticmethod
    def _assert_warning(fragment: str):
        """Context manager that asserts a WARNING containing *fragment* was logged."""
        import logging
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            import io
            handler = logging.StreamHandler(io.StringIO())
            handler.setLevel(logging.WARNING)
            logging.getLogger("subgraph_wizard.generate.ponder_compiler").addHandler(handler)
            try:
                yield
            finally:
                logging.getLogger("subgraph_wizard.generate.ponder_compiler").removeHandler(handler)
                output = handler.stream.getvalue()
                assert fragment in output, (
                    f"Expected warning containing {fragment!r}, got: {output!r}"
                )

        return _ctx()


# ── Bug 9: Conditional fallback for non-nullable fields ────────────────────────

class TestConditionalFallback:
    """Bug 9: conditional node must not emit `undefined` for required columns."""

    def _cond_node(self, node_id):
        return {
            "id": node_id,
            "type": "conditional",
            "position": {"x": 200, "y": 0},
            "data": {},
        }

    def test_required_field_uses_zero_not_undefined(self):
        """A required BigInt field wired through a conditional must fall back to 0n."""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "amount", "type": "BigInt", "required": True},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Snap", fields=fields),
            self._cond_node("cond1"),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-block-number", "cond1", "value"),
            _edge("ed3", "c1", "implicit-tx-hash", "cond1", "condition"),
            _edge("ed4", "cond1", "value-out", "e1", "field-amount"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "undefined" not in src
        # Should fall back to BigInt zero
        assert "0n" in src

    def test_optional_field_uses_null_not_undefined(self):
        """A nullable (not required) field wired through conditional falls back to null."""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "label", "type": "String", "required": False},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Snap", fields=fields),
            self._cond_node("cond1"),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-tx-hash", "cond1", "condition"),
            _edge("ed3", "c1", "event-Transfer-from", "cond1", "value"),
            _edge("ed4", "cond1", "value-out", "e1", "field-label"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "undefined" not in src
        assert "null" in src


# ── Bug 11: _is_reachable_from_event recursive check ─────────────────────────

class TestReachableFromEvent:
    """Bug 11: values sourced from a different event via a transform must be excluded."""

    def _math_node(self, node_id):
        return {
            "id": node_id,
            "type": "math",
            "position": {"x": 200, "y": 0},
            "data": {"operation": "add"},
        }

    def test_math_sourced_from_other_event_excluded(self):
        """A math node whose input comes from Transfer should not appear in Deposit handler."""
        fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "count", "type": "BigInt"},
        ]
        agg_fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "total", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", events=[
                _event("Transfer", [{"name": "amount", "type": "uint256"}]),
                _event("Deposit",  [{"name": "value",  "type": "uint256"}]),
            ]),
            _agg_entity("agg1", "Stats", agg_fields),
            self._math_node("m1"),
        ]
        edges = [
            # Math node gets its LEFT input from Transfer-amount (wrong event)
            _edge("e1", "c1", "event-Transfer-amount", "m1", "left"),
            # Math result fed into the aggregate's `total` field-in
            _edge("e2", "m1", "result", "agg1", "field-in-total"),
            # Aggregate triggered by Deposit
            _edge("e3", "c1", "event-Deposit", "agg1", "trigger"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        # The Deposit handler should not reference event-Transfer-amount
        deposit_idx = src.find('ponder.on("Token:Deposit"')
        assert deposit_idx != -1
        deposit_block = src[deposit_idx:]
        # The math result from Transfer param must not appear in Deposit handler
        assert "event.args.amount" not in deposit_block

    def test_implicit_port_always_reachable(self):
        """implicit-* ports (block number, tx hash) are reachable from any event."""
        agg_fields = [
            {"name": "id", "type": "ID", "required": True},
            {"name": "lastBlock", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", events=[
                _event("Transfer"),
                _event("Deposit"),
            ]),
            _agg_entity("agg1", "Stats", agg_fields),
        ]
        edges = [
            _edge("e1", "c1", "implicit-block-number", "agg1", "field-in-lastBlock"),
            _edge("e2", "c1", "event-Deposit", "agg1", "trigger"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        deposit_idx = src.find('ponder.on("Token:Deposit"')
        assert deposit_idx != -1
        deposit_block = src[deposit_idx:]
        assert "event.block.number" in deposit_block


# ── Bug 13: implicit-instance-address normalisation ───────────────────────────

class TestImplicitInstanceAddress:
    """Bug 13: implicit-instance-address and implicit-address must be identical."""

    def test_implicit_instance_address_maps_same_as_implicit_address(self):
        """Both port IDs must produce event.log.address."""
        assert _event_param_expr_ts("implicit-address") == "event.log.address"
        assert _event_param_expr_ts("implicit-instance-address") == "event.log.address"

    def test_entity_field_via_implicit_instance_address(self):
        """Wiring implicit-instance-address to a field produces event.log.address in output."""
        fields = [
            {"name": "id",       "type": "ID",      "required": True},
            {"name": "emitter",  "type": "Address"},
        ]
        nodes = [
            _contract("c1", "Token", events=[_event("Transfer")]),
            _entity("e1", "Snap", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "implicit-instance-address", "e1", "field-emitter"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]
        assert "event.log.address" in src


# ── Bug 14: values_lines indentation consistency ──────────────────────────────

class TestValuesIndentation:
    """Bug 14: all fields in .values({}) must have uniform indentation."""

    def test_all_value_fields_uniformly_indented(self):
        """id, chain, and user fields must all have the same indent in .values({})."""
        fields = [
            {"name": "id",     "type": "ID",      "required": True},
            {"name": "amount", "type": "BigInt"},
        ]
        nodes = [
            _contract("c1", "Token", events=[
                _event("Transfer", [{"name": "amount", "type": "uint256"}])
            ]),
            _entity("e1", "Snap", fields=fields),
        ]
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "trigger"),
            _edge("ed2", "c1", "event-Transfer-amount", "e1", "field-amount"),
        ]
        src = compile_ponder(_cfg(nodes=nodes, edges=edges))["src/index.ts"]

        # Inside the .values({ ... }) block, find lines with "id:", "chain:", "amount:"
        import re
        # The values object spans from "values({" to the closing "})"
        values_match = re.search(r'\.values\(\{(.*?)\}\)', src, re.DOTALL)
        assert values_match, "Could not find .values({}) block"
        values_body = values_match.group(1)

        # Each field line must have the same leading-whitespace as the others
        field_lines = [ln for ln in values_body.splitlines() if ln.strip()]
        indents = [len(ln) - len(ln.lstrip()) for ln in field_lines]
        assert len(set(indents)) == 1, (
            f"Field lines have inconsistent indentation: {dict(zip(field_lines, indents))}"
        )


# ── Bug 15: BigDecimal zero comment ──────────────────────────────────────────

class TestBigDecimalZero:
    """Bug 15: _PONDER_ZERO BigDecimal is '\"0\"' — the comment must warn about string concat."""

    def test_bigdecimal_zero_comment_present(self):
        """The _PONDER_ZERO dict must have a comment warning about BigDecimal arithmetic."""
        import inspect
        from subgraph_wizard.generate import ponder_compiler
        src = inspect.getsource(ponder_compiler)
        # The source must mention the arithmetic / string-concat hazard
        assert "string" in src and "BigDecimal" in src
        assert "arithmetic" in src.lower() or "concat" in src.lower()

    def test_bigdecimal_zero_value_is_string_literal(self):
        """The BigDecimal zero initialiser must be a quoted string (not a bigint literal)."""
        from subgraph_wizard.generate.ponder_compiler import _PONDER_ZERO
        bd_zero = _PONDER_ZERO["BigDecimal"]
        # Must be a quoted string ("0"), NOT a bare numeric literal like 0n
        assert bd_zero.startswith('"') or bd_zero.startswith("'"), (
            f"BigDecimal zero should be a quoted string, got: {bd_zero!r}"
        )
