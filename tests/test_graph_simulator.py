"""Tests for generate/graph_simulator.py."""

import pytest
from subgraph_wizard.generate.graph_simulator import simulate_graph, GraphSimulator

# ── Helpers (mirrored from test_graph_compiler.py) ────────────────────────────

def _make_config(nodes, edges):
    return {"schema_version": 1, "subgraph_name": "test", "networks": [], "nodes": nodes, "edges": edges}


def _contract_node(node_id, name, events=None, read_fns=None, instances=None):
    return {
        "id": node_id,
        "type": "contract",
        "position": {"x": 0, "y": 0},
        "data": {
            "name": name,
            "abi": [],
            "events": events or [],
            "readFunctions": read_fns or [],
            "instances": instances or [{"label": "main", "address": "0xAAA", "startBlock": 1}],
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


def _aggregate_node(node_id, name, fields=None, trigger_events=None):
    return {
        "id": node_id,
        "type": "aggregateentity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
            "triggerEvents": trigger_events or [],
        },
    }


def _contractread_node(node_id, contract_node_id, fn_index=0):
    return {
        "id": node_id,
        "type": "contractread",
        "position": {"x": 200, "y": 0},
        "data": {"contractNodeId": contract_node_id, "fnIndex": fn_index},
    }


def _math_node(node_id, operation="add"):
    return {
        "id": node_id, "type": "math", "position": {"x": 200, "y": 0},
        "data": {"operation": operation},
    }


def _typecast_node(node_id, cast_index=1):  # 1 = toString
    return {
        "id": node_id, "type": "typecast", "position": {"x": 200, "y": 0},
        "data": {"castIndex": cast_index},
    }


def _strconcat_node(node_id):
    return {
        "id": node_id, "type": "strconcat", "position": {"x": 200, "y": 0},
        "data": {"separator": ""},
    }


def _conditional_node(node_id):
    return {
        "id": node_id, "type": "conditional", "position": {"x": 200, "y": 0},
        "data": {},
    }


def _edge(eid, src, src_h, tgt, tgt_h):
    return {"id": eid, "source": src, "sourceHandle": src_h, "target": tgt, "targetHandle": tgt_h}


DEPOSIT_EVENT = {
    "name": "Deposit",
    "signature": "Deposit(address,uint256)",
    "params": [
        {"name": "user",   "solidity_type": "address", "graph_type": "Address"},
        {"name": "amount", "solidity_type": "uint256",  "graph_type": "BigInt"},
    ],
}

WITHDRAW_EVENT = {
    "name": "Withdraw",
    "signature": "Withdraw(address,uint256)",
    "params": [
        {"name": "user",   "solidity_type": "address", "graph_type": "Address"},
        {"name": "amount", "solidity_type": "uint256",  "graph_type": "BigInt"},
    ],
}

BALANCE_OF_FN = {
    "name": "balanceOf",
    "inputs":  [{"name": "account", "solidity_type": "address", "graph_type": "Address"}],
    "outputs": [{"name": "param0",  "solidity_type": "uint256",  "graph_type": "BigInt"}],
}


# ── Empty graph ───────────────────────────────────────────────────────────────

class TestEmptyGraph:
    def test_empty_config_returns_empty_lists(self):
        result = simulate_graph(_make_config([], []))
        assert result["handlers"] == []
        assert result["schema"] == []
        assert result["queries"] == []

    def test_contract_with_no_events_no_handlers(self):
        node = _contract_node("c1", "ERC20", events=[])
        result = simulate_graph(_make_config([node], []))
        assert result["handlers"] == []

    def test_unnamed_contract_skipped(self):
        node = _contract_node("c1", "")
        result = simulate_graph(_make_config([node], []))
        assert result["handlers"] == []


# ── Schema ────────────────────────────────────────────────────────────────────

class TestSchema:
    def test_entity_appears_in_schema(self):
        entity = _entity_node("e1", "Transfer", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "value", "type": "BigInt",  "required": False},
        ])
        result = simulate_graph(_make_config([entity], []))
        assert len(result["schema"]) == 1
        s = result["schema"][0]
        assert s["name"] == "Transfer"
        assert s["is_aggregate"] is False
        assert any(f["name"] == "value" for f in s["fields"])

    def test_aggregate_entity_has_is_aggregate_true(self):
        agg = _aggregate_node("a1", "TVL", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "total", "type": "BigInt", "required": False},
        ])
        result = simulate_graph(_make_config([agg], []))
        assert result["schema"][0]["is_aggregate"] is True

    def test_unnamed_entity_skipped_in_schema(self):
        entity = _entity_node("e1", "")
        result = simulate_graph(_make_config([entity], []))
        assert result["schema"] == []

    def test_derived_from_field_included_in_schema(self):
        entity = _entity_node("e1", "Pool", fields=[
            {"name": "id",       "type": "ID",      "required": True},
            {"name": "deposits", "type": "Deposit",  "required": False,
             "derivedFrom": "pool"},
        ])
        result = simulate_graph(_make_config([entity], []))
        fields = result["schema"][0]["fields"]
        derived = next(f for f in fields if f["name"] == "deposits")
        assert derived["derivedFrom"] == "pool"

    def test_required_flag_preserved(self):
        entity = _entity_node("e1", "Foo", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "count", "type": "BigInt",  "required": True},
        ])
        result = simulate_graph(_make_config([entity], []))
        fields = {f["name"]: f for f in result["schema"][0]["fields"]}
        assert fields["id"]["required"] is True
        assert fields["count"]["required"] is True


# ── Queries ───────────────────────────────────────────────────────────────────

class TestQueries:
    def test_query_names_camel_cased(self):
        entity = _entity_node("e1", "TransferEvent")
        result = simulate_graph(_make_config([entity], []))
        q = result["queries"][0]
        assert q["singular"] == "transferEvent"
        assert q["plural"]   == "transferEvents"

    def test_query_lists_non_derived_fields(self):
        entity = _entity_node("e1", "Transfer", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "value", "type": "BigInt",  "required": False},
            {"name": "logs",  "type": "Log",     "required": False, "derivedFrom": "transfer"},
        ])
        result = simulate_graph(_make_config([entity], []))
        q = result["queries"][0]
        assert "id" in q["fields"]
        assert "value" in q["fields"]
        assert "logs" not in q["fields"]   # derivedFrom excluded

    def test_one_query_per_entity(self):
        e1 = _entity_node("e1", "Foo")
        e2 = _entity_node("e2", "Bar")
        result = simulate_graph(_make_config([e1, e2], []))
        names = {q["entity"] for q in result["queries"]}
        assert names == {"Foo", "Bar"}


# ── Handlers — basic ─────────────────────────────────────────────────────────

class TestHandlers:
    def _config_with_wire(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity   = _entity_node("e1", "DepositRecord", fields=[
            {"name": "id",     "type": "ID",    "required": True},
            {"name": "amount", "type": "BigInt", "required": False},
        ])
        edges = [
            _edge("edge1", "c1", "event-Deposit", "e1", "field-id"),
            _edge("edge2", "c1", "event-Deposit-amount", "e1", "field-amount"),
        ]
        return _make_config([contract, entity], edges)

    def test_handler_generated_for_wired_event(self):
        result = simulate_graph(self._config_with_wire())
        assert len(result["handlers"]) == 1
        h = result["handlers"][0]
        assert h["contract"] == "Vault"
        assert h["event"]    == "Deposit"

    def test_handler_contains_entity_load_step(self):
        result = simulate_graph(self._config_with_wire())
        steps = result["handlers"][0]["steps"]
        assert any(s["type"] == "entity_load" for s in steps)

    def test_handler_contains_entity_save_step(self):
        result = simulate_graph(self._config_with_wire())
        steps = result["handlers"][0]["steps"]
        assert any(s["type"] == "entity_save" for s in steps)

    def test_handler_contains_field_write_step(self):
        result = simulate_graph(self._config_with_wire())
        steps = result["handlers"][0]["steps"]
        writes = [s for s in steps if s["type"] == "field_write"]
        assert any(s["field"] == "amount" for s in writes)

    def test_event_with_no_entities_skipped(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        result = simulate_graph(_make_config([contract], []))
        assert result["handlers"] == []

    def test_step_order_load_before_write_before_save(self):
        result = simulate_graph(self._config_with_wire())
        steps = result["handlers"][0]["steps"]
        types = [s["type"] for s in steps]
        load_idx  = types.index("entity_load")
        write_idx = types.index("field_write")
        save_idx  = types.index("entity_save")
        assert load_idx < write_idx < save_idx


# ── Handler — value source descriptions ───────────────────────────────────────

class TestValueDescriptions:
    def _config_with_implicit_port(self, port_id, field_name):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id",        "type": "ID",    "required": True},
            {"name": field_name,  "type": "BigInt", "required": False},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "e1", "field-id"),
            _edge("e2", "c1", port_id, "e1", f"field-{field_name}"),
        ]
        return _make_config([contract, entity], edges)

    def test_event_param_described(self):
        result = simulate_graph(self._config_with_implicit_port(
            "event-Deposit-amount", "amount"
        ))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "amount")
        assert "Deposit" in write["source"]
        assert "amount" in write["source"]
        assert "event parameter" in write["source"]

    def test_block_number_described(self):
        result = simulate_graph(self._config_with_implicit_port(
            "implicit-block-number", "blockNum"
        ))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "blockNum")
        assert "block" in write["source"].lower()
        assert "number" in write["source"].lower()

    def test_block_timestamp_described(self):
        result = simulate_graph(self._config_with_implicit_port(
            "implicit-block-timestamp", "ts"
        ))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "ts")
        assert "block" in write["source"].lower()
        assert "timestamp" in write["source"].lower()

    def test_deployed_address_described(self):
        result = simulate_graph(self._config_with_implicit_port(
            "implicit-instance-address", "addr"
        ))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "addr")
        assert "deployed address" in write["source"]

    def test_event_param_hyphenated_port_id(self):
        """Event params with hyphens in names should parse correctly."""
        # Port ID: event-Transfer-my-param (param name = "my-param")
        sim = GraphSimulator(_make_config([], []))
        # Inject a fake contract node
        sim._nodes["c1"] = {"type": "contract", "data": {"name": "Token"}}
        result = sim._describe_value("c1", "event-Transfer-my-param", "Transfer")
        assert "Transfer" in result
        assert "my-param" in result
        assert "event parameter" in result

    def test_math_node_described(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        math     = _math_node("m1", operation="add")
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "total", "type": "BigInt", "required": False},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit",        "e1",  "field-id"),
            _edge("e2", "c1", "event-Deposit-amount", "m1",  "left"),
            _edge("e3", "c1", "event-Deposit-amount", "m1",  "right"),
            _edge("e4", "m1", "result",               "e1",  "field-total"),
        ]
        result = simulate_graph(_make_config([contract, math, entity], edges))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "total")
        assert "+" in write["source"]

    def test_typecast_node_described(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        tc       = _typecast_node("tc1", cast_index=1)  # → String
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id",  "type": "ID",     "required": True},
            {"name": "key", "type": "String",  "required": False},
        ])
        edges = [
            _edge("e1", "c1",  "event-Deposit",         "e1",  "field-id"),
            _edge("e2", "c1",  "implicit-block-number",  "tc1", "value"),
            _edge("e3", "tc1", "result",                 "e1",  "field-key"),
        ]
        result = simulate_graph(_make_config([contract, tc, entity], edges))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "key")
        assert "String" in write["source"] or "toString" in write["source"]

    def test_strconcat_node_described(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        sc       = _strconcat_node("sc1")
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "label", "type": "String", "required": False},
        ])
        edges = [
            _edge("e1", "c1",  "event-Deposit",         "e1",  "field-id"),
            _edge("e2", "c1",  "implicit-block-number",  "sc1", "left"),
            _edge("e3", "c1",  "implicit-tx-hash",       "sc1", "right"),
            _edge("e4", "sc1", "result",                 "e1",  "field-label"),
        ]
        result = simulate_graph(_make_config([contract, sc, entity], edges))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "label")
        assert "concat" in write["source"]

    def test_conditional_node_described(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        cond     = _conditional_node("cond1")
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id",  "type": "ID",    "required": True},
            {"name": "val", "type": "BigInt", "required": False},
        ])
        edges = [
            _edge("e1", "c1",    "event-Deposit",         "e1",    "field-id"),
            _edge("e2", "c1",    "event-Deposit-amount",  "cond1", "value"),
            _edge("e3", "c1",    "event-Deposit-amount",  "cond1", "condition"),
            _edge("e4", "cond1", "value-out",             "e1",    "field-val"),
        ]
        result = simulate_graph(_make_config([contract, cond, entity], edges))
        steps = result["handlers"][0]["steps"]
        write = next(s for s in steps if s["type"] == "field_write" and s["field"] == "val")
        assert "if" in write["source"]


# ── Handler — ID field ────────────────────────────────────────────────────────

class TestIdField:
    def test_wired_id_shows_source(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id", "type": "ID", "required": True},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit",      "e1", "field-id"),
            # id wired to the event trigger port (common pattern)
        ]
        result = simulate_graph(_make_config([contract, entity], edges))
        steps = result["handlers"][0]["steps"]
        load = next(s for s in steps if s["type"] == "entity_load")
        # Should show something meaningful, not the tx.hash fallback
        assert "transaction hash" not in load["id_source"]

    def test_unwired_id_shows_fallback_warning(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id",  "type": "ID",    "required": True},
            {"name": "val", "type": "BigInt", "required": False},
        ])
        edges = [
            # Wire the event trigger so the entity is discovered (id field left unwired)
            _edge("trig", "c1", "event-Deposit", "e1", "evt"),
            _edge("val",  "c1", "event-Deposit-amount", "e1", "field-val"),
        ]
        result = simulate_graph(_make_config([contract, entity], edges))
        steps = result["handlers"][0]["steps"]
        load = next(s for s in steps if s["type"] == "entity_load")
        assert "transaction hash" in load["id_source"]
        assert "wire" in load["id_source"].lower() or "stable" in load["id_source"].lower()


# ── Contract Read in handler ──────────────────────────────────────────────────

class TestContractReadInHandler:
    def _config(self):
        myt_contract = _contract_node(
            "myt", "MYT", read_fns=[BALANCE_OF_FN],
            instances=[{"label": "main", "address": "0xMYT", "startBlock": 1}],
        )
        alchemist = _contract_node("alch", "Alchemist", events=[DEPOSIT_EVENT],
                                   instances=[{"label": "main", "address": "0xALCH", "startBlock": 1}])
        cr = _contractread_node("cr1", "myt", fn_index=0)
        agg = _aggregate_node("agg1", "TVL", fields=[
            {"name": "id",  "type": "ID",    "required": True},
            {"name": "tvl", "type": "BigInt", "required": False},
        ], trigger_events=[{"contractId": "alch", "contractName": "Alchemist", "eventName": "Deposit"}])
        edges = [
            # Alchemist deployed address → CR account argument
            _edge("e1", "alch", "implicit-instance-address", "cr1",  "in-account"),
            # CR param0 → TVL field
            _edge("e2", "cr1",  "out-param0",               "agg1", "field-in-tvl"),
            # TVL id wired to alchemist deployed address via typecast
        ]
        return _make_config([myt_contract, alchemist, cr, agg], edges)

    def test_contract_read_step_appears(self):
        result = simulate_graph(self._config())
        # Find the Deposit handler
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        reads = [s for s in h["steps"] if s["type"] == "contract_read"]
        assert len(reads) >= 1

    def test_contract_read_label_contains_function_name(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        reads = [s for s in h["steps"] if s["type"] == "contract_read"]
        assert any("balanceOf" in r["label"] for r in reads)

    def test_contract_read_bind_uses_instance_address(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        reads = [s for s in h["steps"] if s["type"] == "contract_read"]
        read = next(r for r in reads if "balanceOf" in r["label"])
        assert "0xMYT" in read["bind"]

    def test_contract_read_arg_described(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        reads = [s for s in h["steps"] if s["type"] == "contract_read"]
        read = next(r for r in reads if "balanceOf" in r["label"])
        assert len(read["args"]) == 1
        assert "account" in read["args"][0]
        assert "unwired" not in read["args"][0]

    def test_contract_read_result_field_write(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        writes = [s for s in h["steps"] if s["type"] == "field_write"]
        tvl_write = next((s for s in writes if s["field"] == "tvl"), None)
        assert tvl_write is not None
        assert "balanceOf" in tvl_write["source"] or "MYT" in tvl_write["source"]


# ── Aggregate entity ──────────────────────────────────────────────────────────

class TestAggregateEntity:
    def _config(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        agg = _aggregate_node("agg1", "Stats", fields=[
            {"name": "id",       "type": "ID",    "required": True},
            {"name": "deposits", "type": "BigInt", "required": False},
            {"name": "unwired",  "type": "BigInt", "required": False},
        ], trigger_events=[{"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}])
        edges = [
            _edge("e1", "c1", "event-Deposit-amount", "agg1", "field-in-deposits"),
        ]
        return _make_config([contract, agg], edges)

    def test_aggregate_handler_generated(self):
        result = simulate_graph(self._config())
        assert any(h["event"] == "Deposit" for h in result["handlers"])

    def test_wired_field_produces_field_write(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        writes = [s for s in h["steps"] if s["type"] == "field_write"]
        assert any(s["field"] == "deposits" for s in writes)

    def test_unwired_field_produces_field_unchanged(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        unchanged = [s for s in h["steps"] if s["type"] == "field_unchanged"]
        assert any(s["field"] == "unwired" for s in unchanged)

    def test_aggregate_appears_in_schema(self):
        result = simulate_graph(self._config())
        schema = {s["name"]: s for s in result["schema"]}
        assert "Stats" in schema
        assert schema["Stats"]["is_aggregate"] is True


# ── Multi-event aggregate (triggerEvents checklist) ───────────────────────────

class TestMultiTriggerAggregate:
    def _config(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT, WITHDRAW_EVENT])
        agg = _aggregate_node("agg1", "TVL", fields=[
            {"name": "id",  "type": "ID",    "required": True},
            {"name": "tvl", "type": "BigInt", "required": False},
        ], trigger_events=[
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"},
            {"contractId": "c1", "contractName": "Vault", "eventName": "Withdraw"},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit-amount",  "agg1", "field-in-tvl"),
            _edge("e2", "c1", "event-Withdraw-amount", "agg1", "field-in-tvl"),
        ]
        return _make_config([contract, agg], edges)

    def test_two_handlers_generated(self):
        result = simulate_graph(self._config())
        events = {h["event"] for h in result["handlers"]}
        assert "Deposit"  in events
        assert "Withdraw" in events

    def test_deposit_handler_has_tvl_write(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Deposit")
        writes = [s for s in h["steps"] if s["type"] == "field_write"]
        assert any(s["field"] == "tvl" for s in writes)

    def test_withdraw_handler_has_tvl_write(self):
        result = simulate_graph(self._config())
        h = next(h for h in result["handlers"] if h["event"] == "Withdraw")
        writes = [s for s in h["steps"] if s["type"] == "field_write"]
        assert any(s["field"] == "tvl" for s in writes)


# ── Cycle protection in _collect_contract_read_steps ─────────────────────────

class TestCycleProtection:
    def test_transform_cycle_does_not_infinite_loop(self):
        """A math→math cycle (unusual but possible in a broken graph) should
        not cause infinite recursion."""
        m1 = _math_node("m1")
        m2 = _math_node("m2")
        # Create a cycle: m1.result → m2.left, m2.result → m1.left
        # (This is an invalid graph but the simulator should handle it gracefully)
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity   = _entity_node("e1", "Record", fields=[
            {"name": "id",  "type": "ID",    "required": True},
            {"name": "val", "type": "BigInt", "required": False},
        ])
        edges = [
            _edge("edge1", "c1", "event-Deposit",   "e1", "field-id"),
            _edge("edge2", "m1", "result",           "m2", "left"),
            _edge("edge3", "m2", "result",           "m1", "left"),
            _edge("edge4", "m1", "result",           "e1", "field-val"),
        ]
        # Should not raise RecursionError
        result = simulate_graph(_make_config([contract, m1, m2, entity], edges))
        assert result is not None


# ── AggregateEntity output ports ─────────────────────────────────────────────

class TestAggregateOutputPorts:
    def test_field_out_id_described(self):
        sim = GraphSimulator(_make_config([], []))
        sim._nodes["agg1"] = {
            "type": "aggregateentity",
            "data": {"name": "MyAgg", "fields": [], "triggerEvents": []},
        }
        result = sim._describe_value("agg1", "field-out-id", "")
        assert "MyAgg" in result
        assert "ID" in result or "id" in result.lower()

    def test_field_prev_described(self):
        sim = GraphSimulator(_make_config([], []))
        sim._nodes["agg1"] = {
            "type": "aggregateentity",
            "data": {"name": "MyAgg", "fields": [], "triggerEvents": []},
        }
        result = sim._describe_value("agg1", "field-prev-total", "")
        assert "previous" in result
        assert "MyAgg" in result
        assert "total" in result


# ── Miscellaneous ─────────────────────────────────────────────────────────────

class TestMisc:
    def test_missing_source_node_returns_placeholder(self):
        sim = GraphSimulator(_make_config([], []))
        result = sim._describe_value("nonexistent", "port", "")
        assert "missing" in result

    def test_multiple_contracts_multiple_handlers(self):
        c1 = _contract_node("c1", "TokenA", events=[DEPOSIT_EVENT])
        c2 = _contract_node("c2", "TokenB", events=[WITHDRAW_EVENT])
        e1 = _entity_node("e1", "RecA", fields=[{"name": "id", "type": "ID", "required": True}])
        e2 = _entity_node("e2", "RecB", fields=[{"name": "id", "type": "ID", "required": True}])
        edges = [
            _edge("edge1", "c1", "event-Deposit",  "e1", "field-id"),
            _edge("edge2", "c2", "event-Withdraw", "e2", "field-id"),
        ]
        result = simulate_graph(_make_config([c1, c2, e1, e2], edges))
        contracts = {h["contract"] for h in result["handlers"]}
        assert "TokenA" in contracts
        assert "TokenB" in contracts

    def test_contract_read_with_no_instance_shows_fallback(self):
        myt_contract = _contract_node(
            "myt", "MYT", read_fns=[BALANCE_OF_FN], instances=[]
        )
        sim = GraphSimulator(_make_config([myt_contract], []))
        cr_node = _contractread_node("cr1", "myt", fn_index=0)
        sim._nodes["cr1"] = cr_node
        # Describe the result of this contract read
        result = sim._describe_value("cr1", "out-param0", "")
        assert "MYT" in result or "balanceOf" in result


# ── Entity triggerEvents (no-wire multi-trigger for regular entity) ────────────

class TestEntityTriggerEventsSimulator:
    """Regular entity with triggerEvents should produce handler steps
    just like aggregate entity with triggerEvents."""

    def _entity_with_trigger(self, trigger_events):
        return {
            "id": "e1",
            "type": "entity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "DepositRecord",
                "fields": [
                    {"name": "id",     "type": "ID",    "required": True},
                    {"name": "amount", "type": "BigInt", "required": False},
                ],
                "triggerEvents": trigger_events,
            },
        }

    def test_entity_trigger_events_produces_handler(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}
        ])
        result = simulate_graph(_make_config([contract, entity], []))
        assert len(result["handlers"]) == 1
        h = result["handlers"][0]
        assert h["contract"] == "Vault"
        assert h["event"] == "Deposit"

    def test_entity_trigger_multiple_events_produces_multiple_handlers(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT, WITHDRAW_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"},
            {"contractId": "c1", "contractName": "Vault", "eventName": "Withdraw"},
        ])
        result = simulate_graph(_make_config([contract, entity], []))
        events = {h["event"] for h in result["handlers"]}
        assert "Deposit" in events
        assert "Withdraw" in events

    def test_entity_trigger_entity_appears_in_schema(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}
        ])
        result = simulate_graph(_make_config([contract, entity], []))
        schema_names = [s["name"] for s in result["schema"]]
        assert "DepositRecord" in schema_names

    def test_entity_trigger_wrong_contract_produces_no_handler(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "wrong-id", "contractName": "Vault", "eventName": "Deposit"}
        ])
        result = simulate_graph(_make_config([contract, entity], []))
        assert result["handlers"] == []

    def test_entity_trigger_steps_include_load_and_save(self):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}
        ])
        result = simulate_graph(_make_config([contract, entity], []))
        steps = result["handlers"][0]["steps"]
        step_types = [s["type"] for s in steps]
        assert "entity_load" in step_types
        assert "entity_save" in step_types

    def test_entity_trigger_is_not_aggregate(self):
        """Regular entity triggered via checklist should NOT show is_aggregate=True."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}
        ])
        result = simulate_graph(_make_config([contract, entity], []))
        h = result["handlers"][0]
        load_step = next(s for s in h["steps"] if s["type"] == "entity_load")
        assert load_step["is_aggregate"] is False

    def test_entity_trigger_and_wire_combined(self):
        """Entity wired directly to one event and checklist-triggered for another."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT, WITHDRAW_EVENT])
        entity = {
            "id": "e1",
            "type": "entity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "Record",
                "fields": [{"name": "id", "type": "ID", "required": True}],
                "triggerEvents": [
                    {"contractId": "c1", "contractName": "Vault", "eventName": "Withdraw"}
                ],
            },
        }
        edges = [_edge("ev1", "c1", "event-Deposit", "e1", "field-id")]
        result = simulate_graph(_make_config([contract, entity], edges))
        events = {h["event"] for h in result["handlers"]}
        assert "Deposit" in events
        assert "Withdraw" in events


# ── Edge cases: empty/missing event and entity names ─────────────────────────

class TestEdgeCasesSimulator:
    def test_event_with_empty_name_skipped(self):
        """Event with empty name must not crash — handler is silently omitted."""
        bad_event = {"name": "", "signature": "()", "params": []}
        contract = _contract_node("c1", "Vault", events=[bad_event, DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("ev1", "c1", "event-Deposit", "e1", "field-id")]
        result = simulate_graph(_make_config([contract, entity], edges))
        events = [h["event"] for h in result["handlers"]]
        assert "Deposit" in events
        assert "" not in events

    def test_event_missing_name_key_skipped(self):
        """Event dict without 'name' key must not crash."""
        bad_event = {"signature": "()", "params": []}
        contract = _contract_node("c1", "Vault", events=[bad_event, DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record")
        edges = [_edge("ev1", "c1", "event-Deposit", "e1", "field-id")]
        result = simulate_graph(_make_config([contract, entity], edges))
        assert len(result["handlers"]) == 1
        assert result["handlers"][0]["event"] == "Deposit"

    def test_unnamed_aggregate_entity_skipped_in_schema(self):
        """Aggregate entity with empty name must not appear in schema."""
        agg = _aggregate_node("a1", "", fields=[{"name": "id", "type": "ID", "required": True}])
        result = simulate_graph(_make_config([agg], []))
        assert result["schema"] == []

    def test_query_not_generated_for_unnamed_entity(self):
        """Unnamed entity must not appear in queries list."""
        entity = _entity_node("e1", "", fields=[{"name": "id", "type": "ID", "required": True}])
        result = simulate_graph(_make_config([entity], []))
        assert result["queries"] == []
