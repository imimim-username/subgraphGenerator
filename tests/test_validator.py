"""Tests for generate/validator.py."""

import pytest
from subgraph_wizard.generate.validator import validate_graph, has_errors

# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_config(nodes, edges):
    return {
        "schema_version": 1,
        "subgraph_name": "test",
        "networks": [],
        "nodes": nodes,
        "edges": edges,
    }


def _contract_node(node_id, name="MyContract", abi=None, events=None, instances=None):
    return {
        "id": node_id,
        "type": "contract",
        "position": {"x": 0, "y": 0},
        "data": {
            "name": name,
            "abi": abi if abi is not None else [{"type": "event"}],
            "events": events or [],
            "readFunctions": [],
            "instances": instances or [{"label": "main", "address": "0xAAA", "startBlock": 1}],
        },
    }


def _entity_node(node_id, name="MyEntity", fields=None, id_strategy=None):
    data = {
        "name": name,
        "fields": fields or [{"name": "id", "type": "ID", "required": True}],
    }
    if id_strategy is not None:
        data["idStrategy"] = id_strategy
    return {
        "id": node_id,
        "type": "entity",
        "position": {"x": 400, "y": 0},
        "data": data,
    }


def _math_node(node_id):
    return {
        "id": node_id,
        "type": "math",
        "position": {"x": 200, "y": 0},
        "data": {"operation": "add"},
    }


def _strconcat_node(node_id):
    return {
        "id": node_id,
        "type": "strconcat",
        "position": {"x": 200, "y": 0},
        "data": {"separator": ""},
    }


def _edge(eid, src, src_h, tgt, tgt_h):
    return {
        "id": eid,
        "source": src,
        "sourceHandle": src_h,
        "target": tgt,
        "targetHandle": tgt_h,
    }


TRANSFER_EVENT = {
    "name": "Transfer",
    "signature": "Transfer(address,address,uint256)",
    "params": [
        {"name": "from",  "solidity_type": "address", "graph_type": "Address"},
        {"name": "to",    "solidity_type": "address", "graph_type": "Address"},
        {"name": "value", "solidity_type": "uint256",  "graph_type": "BigInt"},
    ],
}


# ── has_errors helper ─────────────────────────────────────────────────────────

class TestHasErrors:
    def test_empty_issues(self):
        assert not has_errors([])

    def test_warning_only(self):
        assert not has_errors([{"level": "warning", "code": "X", "message": "m", "node_id": None, "edge_id": None}])

    def test_error_detected(self):
        assert has_errors([{"level": "error", "code": "X", "message": "m", "node_id": None, "edge_id": None}])

    def test_mixed(self):
        issues = [
            {"level": "warning", "code": "X", "message": "m", "node_id": None, "edge_id": None},
            {"level": "error",   "code": "Y", "message": "m", "node_id": None, "edge_id": None},
        ]
        assert has_errors(issues)


# ── Empty graph ───────────────────────────────────────────────────────────────

class TestEmptyGraph:
    def test_empty_returns_no_issues(self):
        result = validate_graph(_make_config([], []))
        assert result == []


# ── CONTRACT_NO_NAME ─────────────────────────────────────────────────────────

class TestContractNoName:
    def test_detects_missing_name(self):
        node = _contract_node("c1", name="")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACT_NO_NAME" in codes

    def test_named_contract_no_error(self):
        node = _contract_node("c1", name="ERC20")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACT_NO_NAME" not in codes

    def test_error_level(self):
        node = _contract_node("c1", name="")
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "CONTRACT_NO_NAME"]
        assert matching[0]["level"] == "error"

    def test_node_id_attached(self):
        node = _contract_node("c1", name="")
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "CONTRACT_NO_NAME"]
        assert matching[0]["node_id"] == "c1"


# ── CONTRACT_NO_ABI ───────────────────────────────────────────────────────────

class TestContractNoAbi:
    def test_detects_missing_abi(self):
        node = _contract_node("c1", abi=[])
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACT_NO_ABI" in codes

    def test_present_abi_no_error(self):
        node = _contract_node("c1", abi=[{"type": "event"}])
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACT_NO_ABI" not in codes

    def test_error_level(self):
        node = _contract_node("c1", abi=[])
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "CONTRACT_NO_ABI"]
        assert matching[0]["level"] == "error"


# ── DISCONNECTED_CONTRACT ─────────────────────────────────────────────────────

class TestDisconnectedContract:
    def test_contract_with_events_but_no_edges(self):
        node = _contract_node("c1", events=[TRANSFER_EVENT])
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_CONTRACT" in codes

    def test_contract_wired_to_entity_no_warning(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1")
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "field-id")]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_CONTRACT" not in codes

    def test_contract_without_events_no_warning(self):
        node = _contract_node("c1", events=[])
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_CONTRACT" not in codes


# ── ENTITY_NO_NAME ────────────────────────────────────────────────────────────

class TestEntityNoName:
    def test_detects_blank_name(self):
        node = _entity_node("e1", name="")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_NAME" in codes

    def test_named_entity_no_error(self):
        node = _entity_node("e1", name="Transfer")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_NAME" not in codes

    def test_error_level(self):
        node = _entity_node("e1", name="")
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "ENTITY_NO_NAME"]
        assert matching[0]["level"] == "error"


# ── ENTITY_NO_ID_WIRED ────────────────────────────────────────────────────────

class TestEntityNoIdWired:
    def test_detects_missing_id_wire_custom_strategy(self):
        """Custom strategy with no wire → error."""
        entity = _entity_node("e1", name="Evt", id_strategy="custom")
        issues = validate_graph(_make_config([entity], []))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_ID_WIRED" in codes

    def test_detects_missing_id_wire_no_strategy(self):
        """Missing idStrategy defaults to custom → error."""
        entity = _entity_node("e1", name="Evt")  # no id_strategy set
        issues = validate_graph(_make_config([entity], []))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_ID_WIRED" in codes

    def test_wired_id_no_error(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", id_strategy="custom")
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "field-id")]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_ID_WIRED" not in codes

    def test_error_level(self):
        entity = _entity_node("e1", name="Evt", id_strategy="custom")
        issues = validate_graph(_make_config([entity], []))
        matching = [i for i in issues if i["code"] == "ENTITY_NO_ID_WIRED"]
        assert matching[0]["level"] == "error"

    def test_tx_hash_strategy_no_id_wire_required(self):
        """tx_hash strategy auto-generates id — no wire needed."""
        entity = _entity_node("e1", name="Evt", id_strategy="tx_hash")
        issues = validate_graph(_make_config([entity], []))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_ID_WIRED" not in codes

    def test_tx_hash_log_strategy_no_id_wire_required(self):
        """tx_hash_log strategy auto-generates id — no wire needed."""
        entity = _entity_node("e1", name="Evt", id_strategy="tx_hash_log")
        issues = validate_graph(_make_config([entity], []))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_ID_WIRED" not in codes

    def test_event_address_strategy_no_id_wire_required(self):
        """event_address strategy auto-generates id — no wire needed."""
        entity = _entity_node("e1", name="Evt", id_strategy="event_address")
        issues = validate_graph(_make_config([entity], []))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_ID_WIRED" not in codes


# ── DISCONNECTED_ENTITY ────────────────────────────────────────────────────────

class TestDisconnectedEntity:
    def test_entity_with_no_incoming_edges(self):
        entity = _entity_node("e1", name="Evt")
        issues = validate_graph(_make_config([entity], []))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_ENTITY" in codes

    def test_connected_entity_no_warning(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt")
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "field-id")]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_ENTITY" not in codes


# ── ENTITY_NO_FIELDS ──────────────────────────────────────────────────────────

class TestEntityNoFields:
    def test_entity_with_non_id_fields_none_wired(self):
        """ENTITY_NO_FIELDS fires when non-id fields exist but none are wired."""
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "value", "type": "BigInt","required": False},
        ])
        # Only id is wired, value field is NOT wired
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "field-id")]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_FIELDS" in codes

    def test_entity_with_only_id_field_no_warning(self):
        """No ENTITY_NO_FIELDS when there are no non-id fields to wire."""
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[{"name": "id", "type": "ID", "required": True}])
        edges = [_edge("ed1", "c1", "event-Transfer", "e1", "field-id")]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_FIELDS" not in codes

    def test_entity_with_extra_field_wired_no_warning(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[
            {"name": "id",   "type": "ID",    "required": True},
            {"name": "from", "type": "Bytes",  "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("ed2", "c1", "event-Transfer-from", "e1", "field-from"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "ENTITY_NO_FIELDS" not in codes


# ── MATH_DISCONNECTED_INPUT ───────────────────────────────────────────────────

class TestMathDisconnectedInput:
    def test_math_with_no_inputs(self):
        node = _math_node("m1")
        issues = validate_graph(_make_config([node], []))
        math_warns = [i for i in issues if i["code"] == "MATH_DISCONNECTED_INPUT"]
        # Both left and right should warn
        assert len(math_warns) == 2

    def test_math_one_input_wired(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        math = _math_node("m1")
        edges = [_edge("ed1", "c1", "event-Transfer-value", "m1", "left")]
        issues = validate_graph(_make_config([contract, math], edges))
        warn_ports = [i for i in issues if i["code"] == "MATH_DISCONNECTED_INPUT"]
        assert len(warn_ports) == 1

    def test_math_both_inputs_wired_no_warn(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        math = _math_node("m1")
        edges = [
            _edge("ed1", "c1", "event-Transfer-value", "m1", "left"),
            _edge("ed2", "c1", "event-Transfer-value", "m1", "right"),
        ]
        issues = validate_graph(_make_config([contract, math], edges))
        codes = {i["code"] for i in issues}
        assert "MATH_DISCONNECTED_INPUT" not in codes

    def test_strconcat_disconnected_warns(self):
        # strconcat disconnected ports emit STRCONCAT_DISCONNECTED, not MATH_DISCONNECTED_INPUT
        node = _strconcat_node("sc1")
        issues = validate_graph(_make_config([node], []))
        sc_warns = [i for i in issues if i["code"] == "STRCONCAT_DISCONNECTED"]
        assert len(sc_warns) == 2
        # math code should NOT appear on a strconcat node
        math_warns = [i for i in issues if i["code"] == "MATH_DISCONNECTED_INPUT"]
        assert len(math_warns) == 0


# ── TYPE_MISMATCH ─────────────────────────────────────────────────────────────

class TestTypeMismatch:
    def test_compatible_types_no_error(self):
        # BigInt → BigInt field: compatible
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "value", "type": "BigInt", "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("ed2", "c1", "event-Transfer-value", "e1", "field-value"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "TYPE_MISMATCH" not in codes

    def test_incompatible_types_error(self):
        # BigInt → Bytes field: incompatible
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "value", "type": "Bytes", "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("ed2", "c1", "event-Transfer-value", "e1", "field-value"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "TYPE_MISMATCH" in codes

    def test_type_mismatch_is_error_level(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "value", "type": "Bytes", "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("ed2", "c1", "event-Transfer-value", "e1", "field-value"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        matching = [i for i in issues if i["code"] == "TYPE_MISMATCH"]
        assert matching[0]["level"] == "error"

    def test_type_mismatch_has_edge_id(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "value", "type": "Bytes", "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("mismatch-edge", "c1", "event-Transfer-value", "e1", "field-value"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        matching = [i for i in issues if i["code"] == "TYPE_MISMATCH"]
        assert matching[0]["edge_id"] == "mismatch-edge"

    def test_address_to_string_compatible(self):
        # Address → String: compatible per _COMPATIBLE table
        addr_event = {
            "name": "Deposit",
            "signature": "Deposit(address)",
            "params": [{"name": "sender", "solidity_type": "address", "graph_type": "Address"}],
        }
        contract = _contract_node("c1", events=[addr_event])
        entity = _entity_node("e1", name="Dep", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "sender", "type": "String", "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Deposit", "e1", "field-id"),
            _edge("ed2", "c1", "event-Deposit-sender", "e1", "field-sender"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "TYPE_MISMATCH" not in codes

    def test_bigint_to_boolean_incompatible(self):
        bool_event = {
            "name": "Vote",
            "signature": "Vote(uint256)",
            "params": [{"name": "count", "solidity_type": "uint256", "graph_type": "BigInt"}],
        }
        contract = _contract_node("c1", events=[bool_event])
        entity = _entity_node("e1", name="VoteEvt", fields=[
            {"name": "id",    "type": "ID",      "required": True},
            {"name": "count", "type": "Boolean", "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Vote", "e1", "field-id"),
            _edge("ed2", "c1", "event-Vote-count", "e1", "field-count"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "TYPE_MISMATCH" in codes

    def test_implicit_address_port_type(self):
        contract = _contract_node("c1", events=[TRANSFER_EVENT])
        entity = _entity_node("e1", name="Evt", fields=[
            {"name": "id",   "type": "ID",     "required": True},
            {"name": "addr", "type": "Address", "required": False},
        ])
        edges = [
            _edge("ed1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("ed2", "c1", "implicit-address", "e1", "field-addr"),
        ]
        issues = validate_graph(_make_config([contract, entity], edges))
        codes = {i["code"] for i in issues}
        assert "TYPE_MISMATCH" not in codes


# ── validate_graph return structure ──────────────────────────────────────────

class TestIssueStructure:
    def test_issue_has_required_keys(self):
        node = _entity_node("e1", name="")
        issues = validate_graph(_make_config([node], []))
        for issue in issues:
            assert "level" in issue
            assert "code" in issue
            assert "message" in issue
            assert "node_id" in issue
            assert "edge_id" in issue

    def test_issue_levels_are_valid(self):
        node = _contract_node("c1", name="", events=[TRANSFER_EVENT])
        issues = validate_graph(_make_config([node], []))
        for issue in issues:
            assert issue["level"] in ("error", "warning")


# ── Helpers for new node types ────────────────────────────────────────────────

def _typecast_node(node_id, cast_index=0):
    return {
        "id": node_id,
        "type": "typecast",
        "position": {"x": 200, "y": 0},
        "data": {"castIndex": cast_index},
    }


def _conditional_node(node_id):
    return {
        "id": node_id,
        "type": "conditional",
        "position": {"x": 200, "y": 0},
        "data": {},
    }


def _contractread_node(node_id, contract_node_id="", fn_index=0):
    return {
        "id": node_id,
        "type": "contractread",
        "position": {"x": 300, "y": 0},
        "data": {"contractNodeId": contract_node_id, "fnIndex": fn_index},
    }


# ── TYPECAST_BAD_INDEX ────────────────────────────────────────────────────────

class TestTypeCastValidation:
    def test_valid_cast_index_no_warn(self):
        for idx in range(7):  # 0–6 are valid
            node = _typecast_node("tc1", cast_index=idx)
            issues = validate_graph(_make_config([node], []))
            codes = {i["code"] for i in issues}
            assert "TYPECAST_BAD_INDEX" not in codes, f"index {idx} should be valid"

    def test_negative_cast_index_warns(self):
        node = _typecast_node("tc1", cast_index=-1)
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "TYPECAST_BAD_INDEX" in codes

    def test_out_of_range_cast_index_warns(self):
        node = _typecast_node("tc1", cast_index=7)
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "TYPECAST_BAD_INDEX" in codes

    def test_non_int_cast_index_warns(self):
        node = _typecast_node("tc1", cast_index="auto")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "TYPECAST_BAD_INDEX" in codes

    def test_bad_index_is_warning_level(self):
        node = _typecast_node("tc1", cast_index=99)
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "TYPECAST_BAD_INDEX"]
        assert len(matching) == 1
        assert matching[0]["level"] == "warning"
        assert matching[0]["node_id"] == "tc1"


# ── CONDITIONAL_NO_CONDITION ──────────────────────────────────────────────────

class TestConditionalValidation:
    def test_conditional_no_condition_warns(self):
        node = _conditional_node("cond1")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONDITIONAL_NO_CONDITION" in codes

    def test_conditional_with_condition_wired_no_warn(self):
        contract = _contract_node("c1", events=[{
            "name": "Vote",
            "signature": "Vote(bool)",
            "params": [{"name": "approve", "solidity_type": "bool", "graph_type": "Boolean"}],
        }])
        cond = _conditional_node("cond1")
        edges = [_edge("e1", "c1", "event-Vote-approve", "cond1", "condition")]
        issues = validate_graph(_make_config([contract, cond], edges))
        codes = {i["code"] for i in issues}
        assert "CONDITIONAL_NO_CONDITION" not in codes

    def test_conditional_warn_is_warning_level(self):
        node = _conditional_node("cond1")
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "CONDITIONAL_NO_CONDITION"]
        assert len(matching) == 1
        assert matching[0]["level"] == "warning"
        assert matching[0]["node_id"] == "cond1"


# ── CONTRACTREAD_NO_CONTRACT / CONTRACTREAD_BAD_FN_INDEX ─────────────────────

class TestContractReadValidation:
    def _contract_with_read_fn(self, node_id="c1"):
        return {
            "id": node_id,
            "type": "contract",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": "ERC20",
                "abi": [{"type": "function"}],
                "events": [],
                "readFunctions": [
                    {
                        "name": "balanceOf",
                        "inputs": [{"name": "account", "graph_type": "Address"}],
                        "outputs": [{"name": "balance", "graph_type": "BigInt"}],
                    }
                ],
                "instances": [{"label": "main", "address": "0xAAA", "startBlock": 1}],
            },
        }

    def test_no_contract_selected_is_error(self):
        cr = _contractread_node("cr1", contract_node_id="")
        issues = validate_graph(_make_config([cr], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_NO_CONTRACT" in codes

    def test_nonexistent_contract_id_is_error(self):
        cr = _contractread_node("cr1", contract_node_id="nonexistent")
        issues = validate_graph(_make_config([cr], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_NO_CONTRACT" in codes

    def test_no_contract_error_is_error_level(self):
        cr = _contractread_node("cr1", contract_node_id="")
        issues = validate_graph(_make_config([cr], []))
        matching = [i for i in issues if i["code"] == "CONTRACTREAD_NO_CONTRACT"]
        assert len(matching) == 1
        assert matching[0]["level"] == "error"
        assert matching[0]["node_id"] == "cr1"

    def test_valid_fn_index_no_error(self):
        contract = self._contract_with_read_fn()
        cr = _contractread_node("cr1", contract_node_id="c1", fn_index=0)
        issues = validate_graph(_make_config([contract, cr], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_NO_CONTRACT" not in codes
        assert "CONTRACTREAD_BAD_FN_INDEX" not in codes

    def test_fn_index_out_of_range_is_error(self):
        contract = self._contract_with_read_fn()
        cr = _contractread_node("cr1", contract_node_id="c1", fn_index=5)
        issues = validate_graph(_make_config([contract, cr], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_BAD_FN_INDEX" in codes

    def test_negative_fn_index_is_error(self):
        contract = self._contract_with_read_fn()
        cr = _contractread_node("cr1", contract_node_id="c1", fn_index=-1)
        issues = validate_graph(_make_config([contract, cr], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_BAD_FN_INDEX" in codes

    def test_fn_index_error_is_error_level(self):
        contract = self._contract_with_read_fn()
        cr = _contractread_node("cr1", contract_node_id="c1", fn_index=99)
        issues = validate_graph(_make_config([contract, cr], []))
        matching = [i for i in issues if i["code"] == "CONTRACTREAD_BAD_FN_INDEX"]
        assert len(matching) == 1
        assert matching[0]["level"] == "error"
        assert matching[0]["node_id"] == "cr1"


# ── AGGREGATE_NO_NAME / AGGREGATE_NO_ID_WIRED / AGGREGATE_NO_FIELDS / DISCONNECTED_AGGREGATE ──

def _aggregate_node(node_id, name="MyAggregate", fields=None):
    return {
        "id": node_id,
        "type": "aggregateentity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
        },
    }


class TestAggregateEntityNode:
    def test_missing_name_is_error(self):
        node = _aggregate_node("agg1", name="")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "AGGREGATE_NO_NAME" in codes

    def test_named_aggregate_no_name_error(self):
        node = _aggregate_node("agg1", name="AlchemistTVL")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "AGGREGATE_NO_NAME" not in codes

    def test_missing_name_error_is_error_level(self):
        node = _aggregate_node("agg1", name="")
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "AGGREGATE_NO_NAME"]
        assert len(matching) == 1
        assert matching[0]["level"] == "error"
        assert matching[0]["node_id"] == "agg1"

    def test_no_id_wire_is_error(self):
        node = _aggregate_node("agg1", name="AlchemistTVL")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "AGGREGATE_NO_ID_WIRED" in codes

    def test_id_wire_clears_error(self):
        contract = _contract_node("c1", events=[{
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender",  "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount",  "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }])
        agg = _aggregate_node("agg1", name="AlchemistTVL", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "amount", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "agg1", "evt"),
            _edge("e2", "c1", "event-Deposit-sender", "agg1", "field-id"),
            _edge("e3", "c1", "event-Deposit-amount", "agg1", "field-in-amount"),
        ]
        issues = validate_graph(_make_config([contract, agg], edges))
        codes = {i["code"] for i in issues}
        assert "AGGREGATE_NO_ID_WIRED" not in codes

    def test_no_id_wire_error_is_error_level(self):
        node = _aggregate_node("agg1", name="AlchemistTVL")
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "AGGREGATE_NO_ID_WIRED"]
        assert len(matching) == 1
        assert matching[0]["level"] == "error"
        assert matching[0]["node_id"] == "agg1"

    def test_no_field_inputs_wired_warns(self):
        node = _aggregate_node("agg1", name="AlchemistTVL", fields=[
            {"name": "id",     "type": "ID",    "required": True},
            {"name": "amount", "type": "BigInt", "required": False},
        ])
        # Wire id but not field-in-amount
        contract = _contract_node("c1", events=[{
            "name": "Deposit",
            "signature": "Deposit(address)",
            "params": [{"name": "sender", "solidity_type": "address", "graph_type": "Address"}],
        }])
        edges = [
            _edge("e1", "c1", "event-Deposit-sender", "agg1", "field-id"),
        ]
        issues = validate_graph(_make_config([contract, node], edges))
        codes = {i["code"] for i in issues}
        assert "AGGREGATE_NO_FIELDS" in codes

    def test_field_inputs_wired_no_warning(self):
        contract = _contract_node("c1", events=[{
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender",  "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount",  "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }])
        agg = _aggregate_node("agg1", name="AlchemistTVL", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "amount", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "agg1", "evt"),
            _edge("e2", "c1", "event-Deposit-sender", "agg1", "field-id"),
            _edge("e3", "c1", "event-Deposit-amount", "agg1", "field-in-amount"),
        ]
        issues = validate_graph(_make_config([contract, agg], edges))
        codes = {i["code"] for i in issues}
        assert "AGGREGATE_NO_FIELDS" not in codes

    def test_no_incoming_connections_warns(self):
        node = _aggregate_node("agg1", name="AlchemistTVL")
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_AGGREGATE" in codes

    def test_disconnected_aggregate_is_warning_level(self):
        node = _aggregate_node("agg1", name="AlchemistTVL")
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "DISCONNECTED_AGGREGATE"]
        assert len(matching) == 1
        assert matching[0]["level"] == "warning"
        assert matching[0]["node_id"] == "agg1"

    def test_trigger_events_suppresses_disconnected_aggregate_warning(self):
        """Aggregate with triggerEvents but no incoming edges must NOT warn DISCONNECTED_AGGREGATE."""
        node = {
            "id": "agg1",
            "type": "aggregateentity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "VaultTVL",
                "fields": [{"name": "id", "type": "ID", "required": True}],
                "triggerEvents": [
                    {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"},
                ],
            },
        }
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_AGGREGATE" not in codes

    def test_trigger_events_with_no_edges_still_requires_id_wire(self):
        """triggerEvents does not exempt the aggregate from needing its id wired."""
        node = {
            "id": "agg1",
            "type": "aggregateentity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "VaultTVL",
                "fields": [{"name": "id", "type": "ID", "required": True}],
                "triggerEvents": [
                    {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"},
                ],
            },
        }
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        # AGGREGATE_NO_ID_WIRED must still fire — id is always required
        assert "AGGREGATE_NO_ID_WIRED" in codes

    def test_empty_trigger_events_list_still_warns_disconnected(self):
        """An empty triggerEvents list is treated the same as no triggerEvents."""
        node = {
            "id": "agg1",
            "type": "aggregateentity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "VaultTVL",
                "fields": [{"name": "id", "type": "ID", "required": True}],
                "triggerEvents": [],  # empty list — not the same as having triggers
            },
        }
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_AGGREGATE" in codes

    def test_trigger_events_with_id_wire_no_errors(self):
        """Aggregate with triggerEvents and a wired id should have no DISCONNECTED or ID errors."""
        contract = _contract_node("c1", events=[{
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender",  "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount",  "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }])
        agg = {
            "id": "agg1",
            "type": "aggregateentity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "VaultTVL",
                "fields": [
                    {"name": "id",      "type": "ID",     "required": True},
                    {"name": "balance", "type": "BigInt",  "required": False},
                ],
                "triggerEvents": [
                    {"contractId": "c1", "contractName": "MyContract", "eventName": "Deposit"},
                ],
            },
        }
        edges = [
            _edge("e1", "c1", "implicit-address", "agg1", "field-id"),
            _edge("e2", "c1", "event-Deposit-amount", "agg1", "field-in-balance"),
        ]
        issues = validate_graph(_make_config([contract, agg], edges))
        codes = {i["code"] for i in issues}
        assert "DISCONNECTED_AGGREGATE" not in codes
        assert "AGGREGATE_NO_ID_WIRED" not in codes


# ── field-out-id port type + entity-ref fields ────────────────────────────────

class TestFieldOutIdPort:
    """
    Verify that:
      1. field-out-id source port type is "ID" (no type mismatch to entity-ref field)
      2. Entity-ref typed target fields don't trigger TYPE_MISMATCH errors
    """

    def _make_tvl_history_config(self):
        """AlchemistTVL aggregate → AlchemistTVLHistory entity via field-out-id."""
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", events=[deposit_event])
        tvl = _aggregate_node("tvl1", name="AlchemistTVL", fields=[
            {"name": "id",         "type": "ID",     "required": True},
            {"name": "netBalance", "type": "BigInt",  "required": False},
        ])
        history = _entity_node("h1", name="AlchemistTVLHistory", fields=[
            {"name": "id",  "type": "ID",            "required": True},
            {"name": "tvl", "type": "AlchemistTVL",  "required": False},
        ])
        edges = [
            _edge("e1", "c1",   "event-Deposit",       "tvl1", "evt"),
            _edge("e2", "c1",   "implicit-address",     "tvl1", "field-id"),
            _edge("e3", "c1",   "event-Deposit-amount", "tvl1", "field-in-netBalance"),
            _edge("e4", "c1",   "event-Deposit",        "h1",   "evt"),
            _edge("e5", "c1",   "implicit-tx-hash",     "h1",   "field-id"),
            # field-out-id → entity-ref field — must NOT raise TYPE_MISMATCH
            _edge("e6", "tvl1", "field-out-id",         "h1",   "field-tvl"),
        ]
        return _make_config([contract, tvl, history], edges)

    def test_no_type_mismatch_for_field_out_id(self):
        """Wiring field-out-id to an entity-ref target field must not produce TYPE_MISMATCH."""
        issues = validate_graph(self._make_tvl_history_config())
        type_mismatches = [i for i in issues if i["code"] == "TYPE_MISMATCH"]
        assert type_mismatches == [], f"Unexpected TYPE_MISMATCH: {type_mismatches}"

    def test_no_errors_in_fully_wired_tvl_history(self):
        """A fully wired TVL + History graph must be error-free."""
        issues = validate_graph(self._make_tvl_history_config())
        errors = [i for i in issues if i["level"] == "error"]
        assert errors == [], f"Unexpected errors: {errors}"

    def test_entity_ref_target_field_accepts_any_source(self):
        """
        An entity-ref typed target field (type not in primitives) accepts any
        source — no TYPE_MISMATCH should fire even if source is ID/Bytes.
        """
        contract = _contract_node("c1", events=[{
            "name": "Transfer",
            "signature": "Transfer(address)",
            "params": [{"name": "from", "solidity_type": "address", "graph_type": "Address"}],
        }])
        token = _entity_node("t1", name="Token", fields=[
            {"name": "id",    "type": "ID",    "required": True},
            {"name": "owner", "type": "User",  "required": False},  # entity-ref
        ])
        edges = [
            _edge("e1", "c1", "event-Transfer",      "t1", "evt"),
            _edge("e2", "c1", "event-Transfer-from", "t1", "field-owner"),  # Bytes → entity-ref
        ]
        issues = validate_graph(_make_config([contract, token], edges))
        type_mismatches = [i for i in issues if i["code"] == "TYPE_MISMATCH"]
        assert type_mismatches == []


class TestDerivedFromFieldsValidator:
    """
    @derivedFrom fields have no input port, so they should not appear in edges
    and should not cause any validation issues.
    """

    def test_derived_from_field_not_flagged(self):
        """An entity with a @derivedFrom field and no wire to it must not raise errors."""
        contract = _contract_node("c1", events=[{
            "name": "Deposit",
            "signature": "Deposit(uint256)",
            "params": [{"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"}],
        }])
        # AlchemistTVL has a @derivedFrom 'activity' field — no wire needed/possible
        tvl = _entity_node("e1", name="AlchemistTVL", fields=[
            {"name": "id",       "type": "ID",                  "required": True},
            {"name": "balance",  "type": "BigInt",               "required": False},
            {"name": "activity", "type": "AlchemistTVLHistory",  "required": False,
             "derivedFrom": "tvl"},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit",        "e1", "evt"),
            _edge("e2", "c1", "implicit-tx-hash",     "e1", "field-id"),
            _edge("e3", "c1", "event-Deposit-amount",  "e1", "field-balance"),
        ]
        issues = validate_graph(_make_config([contract, tvl], edges))
        errors = [i for i in issues if i["level"] == "error"]
        assert errors == [], f"Unexpected errors: {errors}"


# ── CONTRACT_START_BLOCK_ZERO ─────────────────────────────────────────────────

class TestStartBlockZero:
    """CONTRACT_START_BLOCK_ZERO warns when a contract instance has startBlock=0."""

    def _contract(self, instances):
        return {
            "id": "c1",
            "type": "contract",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": "MyContract",
                "abi": [{"type": "event"}],
                "events": [],
                "readFunctions": [],
                "instances": instances,
            },
        }

    def test_no_warning_when_start_block_set(self):
        node = self._contract([{"label": "main", "address": "0xAAA", "startBlock": 12345}])
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACT_START_BLOCK_ZERO" not in codes

    def test_warning_when_start_block_zero(self):
        node = self._contract([{"label": "main", "address": "0xAAA", "startBlock": 0}])
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACT_START_BLOCK_ZERO" in codes

    def test_warning_is_level_warning_not_error(self):
        node = self._contract([{"label": "main", "address": "0xAAA", "startBlock": 0}])
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "CONTRACT_START_BLOCK_ZERO"]
        assert matching[0]["level"] == "warning"
        assert matching[0]["node_id"] == "c1"

    def test_warning_when_start_block_missing(self):
        node = self._contract([{"label": "main", "address": "0xAAA"}])
        issues = validate_graph(_make_config([node], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACT_START_BLOCK_ZERO" in codes

    def test_only_one_warning_per_contract_node(self):
        """Even with multiple zero-startBlock instances, only one warning per node."""
        node = self._contract([
            {"label": "inst1", "address": "0xAAA", "startBlock": 0},
            {"label": "inst2", "address": "0xBBB", "startBlock": 0},
        ])
        issues = validate_graph(_make_config([node], []))
        matching = [i for i in issues if i["code"] == "CONTRACT_START_BLOCK_ZERO"]
        assert len(matching) == 1


# ── CONTRACTREAD_NO_BIND_ADDRESS ──────────────────────────────────────────────

class TestContractReadNoBindAddress:
    """CONTRACTREAD_NO_BIND_ADDRESS warns when the referenced contract has no address."""

    def _contract(self, node_id, name, address="", read_fns=None):
        return {
            "id": node_id,
            "type": "contract",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "abi": [{"type": "event"}],
                "events": [],
                "readFunctions": read_fns or [
                    {"name": "foo", "inputs": [], "outputs": [{"name": "val", "graph_type": "BigInt"}]}
                ],
                "instances": [{"label": "main", "address": address, "startBlock": 1}],
            },
        }

    def _cr_node(self, node_id, contract_node_id, fn_index=0):
        return {
            "id": node_id,
            "type": "contractread",
            "position": {"x": 200, "y": 0},
            "data": {"contractNodeId": contract_node_id, "fnIndex": fn_index},
        }

    def test_no_warning_when_address_configured(self):
        contract = self._contract("c1", "Oracle", address="0xABCDEF1234567890ABCDEF1234567890ABCDEF12")
        cr = self._cr_node("cr1", "c1")
        issues = validate_graph(_make_config([contract, cr], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_NO_BIND_ADDRESS" not in codes

    def test_no_warning_when_bind_address_wired(self):
        contract = self._contract("c1", "Oracle", address="")
        cr = self._cr_node("cr1", "c1")
        # Fake a bind-address wire from some source to the contractread node
        bind_edge = {
            "id": "e1", "source": "some_node", "sourceHandle": "out",
            "target": "cr1", "targetHandle": "bind-address",
        }
        issues = validate_graph(_make_config([contract, cr], [bind_edge]))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_NO_BIND_ADDRESS" not in codes

    def test_warning_when_no_address_and_no_wire(self):
        contract = self._contract("c1", "Oracle", address="")
        cr = self._cr_node("cr1", "c1")
        issues = validate_graph(_make_config([contract, cr], []))
        codes = {i["code"] for i in issues}
        assert "CONTRACTREAD_NO_BIND_ADDRESS" in codes

    def test_warning_is_level_warning(self):
        contract = self._contract("c1", "Oracle", address="")
        cr = self._cr_node("cr1", "c1")
        issues = validate_graph(_make_config([contract, cr], []))
        matching = [i for i in issues if i["code"] == "CONTRACTREAD_NO_BIND_ADDRESS"]
        assert matching[0]["level"] == "warning"
        assert matching[0]["node_id"] == "cr1"
