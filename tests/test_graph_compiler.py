"""Tests for generate/graph_compiler.py."""

import pytest
from subgraph_wizard.generate.graph_compiler import compile_graph, GraphCompiler

# ── Minimal visual config helpers ─────────────────────────────────────────────

def _make_config(nodes, edges, networks=None, subgraph_name="test"):
    return {
        "schema_version": 1,
        "subgraph_name": subgraph_name,
        "networks": networks or [],
        "nodes": nodes,
        "edges": edges,
    }


def _contract_node(node_id, name, events=None, read_fns=None):
    return {
        "id": node_id,
        "type": "contract",
        "position": {"x": 0, "y": 0},
        "data": {
            "name": name,
            "abi": [],
            "events": events or [],
            "readFunctions": read_fns or [],
            "instances": [{"label": "main", "address": "0xAAA", "startBlock": 1}],
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


def _math_node(node_id, operation="add"):
    return {
        "id": node_id,
        "type": "math",
        "position": {"x": 200, "y": 0},
        "data": {"operation": operation},
    }


def _typecast_node(node_id, cast_index=0):
    return {
        "id": node_id,
        "type": "typecast",
        "position": {"x": 200, "y": 0},
        "data": {"castIndex": cast_index},
    }


def _strconcat_node(node_id, separator=""):
    return {
        "id": node_id,
        "type": "strconcat",
        "position": {"x": 200, "y": 0},
        "data": {"separator": separator},
    }


def _conditional_node(node_id):
    return {
        "id": node_id,
        "type": "conditional",
        "position": {"x": 200, "y": 0},
        "data": {},
    }


def _edge(eid, src, src_handle, tgt, tgt_handle):
    return {
        "id": eid,
        "source": src,
        "sourceHandle": src_handle,
        "target": tgt,
        "targetHandle": tgt_handle,
    }


TRANSFER_EVENT = {
    "name": "Transfer",
    "signature": "Transfer(address,address,uint256)",
    "params": [
        {"name": "from", "solidity_type": "address", "graph_type": "Address"},
        {"name": "to",   "solidity_type": "address", "graph_type": "Address"},
        {"name": "value","solidity_type": "uint256",  "graph_type": "BigInt"},
    ],
}


# ── Empty graph ───────────────────────────────────────────────────────────────

class TestEmptyGraph:
    def test_empty_config_returns_empty(self):
        result = compile_graph(_make_config([], []))
        assert result == {}

    def test_contract_with_no_name_skipped(self):
        node = _contract_node("c1", "")  # empty name
        result = compile_graph(_make_config([node], []))
        assert result == {}

    def test_contract_with_no_events_produces_empty_handlers(self):
        node = _contract_node("c1", "ERC20", events=[])
        result = compile_graph(_make_config([node], []))
        assert "ERC20" in result
        assert "export function" not in result["ERC20"]


# ── Basic event → entity wiring ───────────────────────────────────────────────

class TestBasicWiring:
    def _simple_config(self):
        contract = _contract_node("c1", "ERC20", events=[TRANSFER_EVENT])
        entity = _entity_node(
            "e1",
            "TransferEvent",
            fields=[
                {"name": "id",   "type": "ID",     "required": True},
                {"name": "from", "type": "Bytes",   "required": True},
                {"name": "to",   "type": "Bytes",   "required": True},
                {"name": "value","type": "BigInt",  "required": True},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),   # not realistic but triggers handler
            _edge("e2", "c1", "event-Transfer", "e1", "field-from"),  # contract → entity shortcut
        ]
        # Note: in the real editor Contract node emits event-{name} to trigger;
        # actual param values come from the event.params.* expressions.
        # For the handler to be generated we just need *some* edge from the
        # event port to the entity.
        return _make_config([contract, entity], edges)

    def test_handler_function_generated(self):
        result = compile_graph(self._simple_config())
        assert "export function handleTransfer" in result["ERC20"]

    def test_handler_takes_event_param(self):
        result = compile_graph(self._simple_config())
        assert "event: TransferEvent" in result["ERC20"]

    def test_entity_load_generated(self):
        result = compile_graph(self._simple_config())
        src = result["ERC20"]
        assert "TransferEvent.load(" in src

    def test_entity_save_generated(self):
        result = compile_graph(self._simple_config())
        assert ".save()" in result["ERC20"]

    def test_import_generated(self):
        result = compile_graph(self._simple_config())
        src = result["ERC20"]
        assert "import" in src
        assert "ERC20" in src


# ── Event param expressions ───────────────────────────────────────────────────

class TestEventParamExpressions:
    def test_event_param_from_resolves(self):
        contract = _contract_node("c1", "ERC20", events=[TRANSFER_EVENT])
        entity = _entity_node(
            "e1", "XferEvent",
            fields=[
                {"name": "id",   "type": "ID",    "required": True},
                {"name": "sender","type": "Bytes", "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", "event-Transfer-from", "e1", "field-sender"),
        ]
        result = compile_graph(_make_config([contract, entity], edges))
        src = result["ERC20"]
        assert "event.params.from" in src

    def test_event_param_value_resolves(self):
        contract = _contract_node("c1", "ERC20", events=[TRANSFER_EVENT])
        entity = _entity_node(
            "e1", "XferEvent",
            fields=[
                {"name": "id",     "type": "ID",    "required": True},
                {"name": "amount", "type": "BigInt", "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", "event-Transfer-value", "e1", "field-amount"),
        ]
        result = compile_graph(_make_config([contract, entity], edges))
        assert "event.params.value" in result["ERC20"]


# ── Math node ─────────────────────────────────────────────────────────────────

class TestMathNode:
    def _math_config(self, operation):
        contract = _contract_node("c1", "Vault", events=[TRANSFER_EVENT])
        math = _math_node("m1", operation=operation)
        entity = _entity_node(
            "e1", "VaultEvent",
            fields=[
                {"name": "id",    "type": "ID",    "required": True},
                {"name": "total", "type": "BigInt", "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", "event-Transfer-value", "m1", "left"),
            _edge("e3", "c1", "event-Transfer-value", "m1", "right"),
            _edge("e4", "m1", "result", "e1", "field-total"),
        ]
        return _make_config([contract, math, entity], edges)

    def test_math_add_uses_plus(self):
        result = compile_graph(self._math_config("add"))
        assert ".plus(" in result["Vault"]

    def test_math_subtract_uses_minus(self):
        result = compile_graph(self._math_config("subtract"))
        assert ".minus(" in result["Vault"]

    def test_math_multiply_uses_times(self):
        result = compile_graph(self._math_config("multiply"))
        assert ".times(" in result["Vault"]

    def test_math_divide_uses_div(self):
        result = compile_graph(self._math_config("divide"))
        assert ".div(" in result["Vault"]

    def test_math_mod_uses_mod(self):
        result = compile_graph(self._math_config("mod"))
        assert ".mod(" in result["Vault"]


# ── TypeCast node ──────────────────────────────────────────────────────────────

class TestTypeCastNode:
    def test_bigint_to_string_cast(self):
        contract = _contract_node("c1", "Token", events=[TRANSFER_EVENT])
        cast = _typecast_node("t1", cast_index=1)  # BigInt → String
        entity = _entity_node(
            "e1", "TokenEvent",
            fields=[
                {"name": "id",      "type": "ID",     "required": True},
                {"name": "amountStr","type": "String", "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", "event-Transfer-value", "t1", "value"),
            _edge("e3", "t1", "result", "e1", "field-amountStr"),
        ]
        result = compile_graph(_make_config([contract, cast, entity], edges))
        assert ".toString()" in result["Token"]


# ── StringConcat node ──────────────────────────────────────────────────────────

class TestStringConcatNode:
    def test_concat_without_separator(self):
        contract = _contract_node("c1", "Token", events=[TRANSFER_EVENT])
        sc = _strconcat_node("sc1", separator="")
        entity = _entity_node(
            "e1", "TokenEvent",
            fields=[
                {"name": "id",    "type": "ID",     "required": True},
                {"name": "combo", "type": "String",  "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", "event-Transfer-from", "sc1", "left"),
            _edge("e3", "c1", "event-Transfer-to",   "sc1", "right"),
            _edge("e4", "sc1", "result", "e1", "field-combo"),
        ]
        result = compile_graph(_make_config([contract, sc, entity], edges))
        src = result["Token"]
        assert ".concat(" in src
        # No separator → no double concat
        assert '"-"' not in src

    def test_concat_with_separator(self):
        contract = _contract_node("c1", "Token", events=[TRANSFER_EVENT])
        sc = _strconcat_node("sc1", separator="-")
        entity = _entity_node(
            "e1", "TokenEvent",
            fields=[
                {"name": "id",    "type": "ID",    "required": True},
                {"name": "combo", "type": "String", "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", "event-Transfer-from", "sc1", "left"),
            _edge("e3", "c1", "event-Transfer-to",   "sc1", "right"),
            _edge("e4", "sc1", "result", "e1", "field-combo"),
        ]
        result = compile_graph(_make_config([contract, sc, entity], edges))
        assert '"-"' in result["Token"]


# ── Conditional node ───────────────────────────────────────────────────────────

class TestConditionalNode:
    def test_conditional_emits_early_return(self):
        contract = _contract_node("c1", "Token", events=[TRANSFER_EVENT])
        cond = _conditional_node("cond1")
        entity = _entity_node(
            "e1", "TokenEvent",
            fields=[
                {"name": "id",    "type": "ID",    "required": True},
                {"name": "amount","type": "BigInt", "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", "event-Transfer-value", "cond1", "condition"),
            _edge("e3", "c1", "event-Transfer-value", "cond1", "value"),
            _edge("e4", "cond1", "value-out", "e1", "field-amount"),
        ]
        result = compile_graph(_make_config([contract, cond, entity], edges))
        assert "if (!" in result["Token"]
        assert "return" in result["Token"]


# ── Multiple events ────────────────────────────────────────────────────────────

class TestMultipleEvents:
    def test_two_events_produce_two_handlers(self):
        approval_event = {
            "name": "Approval",
            "signature": "Approval(address,address,uint256)",
            "params": [
                {"name": "owner",   "solidity_type": "address", "graph_type": "Address"},
                {"name": "spender", "solidity_type": "address", "graph_type": "Address"},
                {"name": "value",   "solidity_type": "uint256",  "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", "ERC20", events=[TRANSFER_EVENT, approval_event])
        e_transfer = _entity_node("et", "TransferEntity", fields=[{"name": "id", "type": "ID", "required": True}])
        e_approval = _entity_node("ea", "ApprovalEntity", fields=[{"name": "id", "type": "ID", "required": True}])
        edges = [
            _edge("e1", "c1", "event-Transfer", "et", "field-id"),
            _edge("e2", "c1", "event-Approval", "ea", "field-id"),
        ]
        result = compile_graph(_make_config([contract, e_transfer, e_approval], edges))
        src = result["ERC20"]
        assert "handleTransfer" in src
        assert "handleApproval" in src

    def test_unwired_event_no_handler(self):
        approval_event = {
            "name": "Approval",
            "signature": "Approval(address,address,uint256)",
            "params": [],
        }
        contract = _contract_node("c1", "ERC20", events=[TRANSFER_EVENT, approval_event])
        entity = _entity_node("et", "XferEntity", fields=[{"name": "id", "type": "ID", "required": True}])
        edges = [
            _edge("e1", "c1", "event-Transfer", "et", "field-id"),
            # Approval is NOT wired
        ]
        result = compile_graph(_make_config([contract, entity], edges))
        src = result["ERC20"]
        assert "handleTransfer" in src
        assert "handleApproval" not in src


# ── Implicit ports ─────────────────────────────────────────────────────────────

class TestImplicitPorts:
    """Test that implicit-* contract ports resolve to the correct event expressions."""

    def _implicit_config(self, implicit_handle: str, field_name: str, field_type: str):
        contract = _contract_node("c1", "Vault", events=[TRANSFER_EVENT])
        entity = _entity_node(
            "e1", "VaultEvent",
            fields=[
                {"name": "id",      "type": "ID",     "required": True},
                {"name": field_name, "type": field_type, "required": False},
            ],
        )
        edges = [
            _edge("e1", "c1", "event-Transfer", "e1", "field-id"),
            _edge("e2", "c1", implicit_handle, "e1", f"field-{field_name}"),
        ]
        return _make_config([contract, entity], edges)

    def test_implicit_address_resolves(self):
        result = compile_graph(self._implicit_config("implicit-address", "emitter", "Address"))
        assert "event.address" in result["Vault"]

    def test_implicit_tx_hash_resolves(self):
        result = compile_graph(self._implicit_config("implicit-tx-hash", "txHash", "Bytes"))
        assert "event.transaction.hash" in result["Vault"]

    def test_implicit_block_number_resolves(self):
        result = compile_graph(self._implicit_config("implicit-block-number", "blockNum", "BigInt"))
        assert "event.block.number" in result["Vault"]

    def test_implicit_block_timestamp_resolves(self):
        result = compile_graph(self._implicit_config("implicit-block-timestamp", "blockTs", "BigInt"))
        assert "event.block.timestamp" in result["Vault"]


# ── ContractRead node ──────────────────────────────────────────────────────────

def _contractread_node(node_id, contract_node_id, fn_index=0):
    return {
        "id": node_id,
        "type": "contractread",
        "position": {"x": 600, "y": 0},
        "data": {
            "contractNodeId": contract_node_id,
            "fnIndex": fn_index,
        },
    }


class TestContractReadNode:
    """Test that contractread nodes compile to correct AssemblyScript."""

    DEPOSIT_EVENT = {
        "name": "Deposit",
        "signature": "Deposit(address,uint256)",
        "params": [
            {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
            {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
        ],
    }

    READ_FN = {
        "name": "balanceOf",
        "signature": "balanceOf(address)",
        "inputs":  [{"name": "account", "solidity_type": "address", "graph_type": "Address"}],
        "outputs": [{"name": "balance", "solidity_type": "uint256", "graph_type": "BigInt"}],
    }

    def _base_config(self, wire_bind_address=False):
        """
        Alchemist contract with Deposit event + MYT contract with balanceOf.
        ContractRead calls MYT.balanceOf(event.params.sender) and stores result.
        """
        alchemist = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        myt = _contract_node("myt1", "MYT", events=[], read_fns=[self.READ_FN])
        cr = _contractread_node("cr1", contract_node_id="myt1")
        entity = _entity_node("e1", "DepositRecord", fields=[
            {"name": "id",      "type": "ID",     "required": True},
            {"name": "balance", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "evt"),
            _edge("ev2", "c1", "implicit-tx-hash", "e1", "field-id"),
            _edge("ev3", "c1", "event-Deposit-sender", "cr1", "in-account"),
            _edge("ev4", "cr1", "out-balance", "e1", "field-balance"),
        ]
        if wire_bind_address:
            edges.append(_edge("ev5", "c1", "implicit-address", "cr1", "bind-address"))
        return _make_config([alchemist, myt, cr, entity], edges)

    def test_bind_uses_instance_address_by_default(self):
        """When bind-address is not wired, the selected contract's first instance
        address is used automatically — the intuitive default for cross-contract reads."""
        result = compile_graph(self._base_config(wire_bind_address=False))
        src = result["Alchemist"]
        # MYT node has instances[0].address = "0xAAA" (set by _contract_node fixture)
        assert 'MYT.bind(Address.fromString("0xAAA"))' in src

    def test_bind_falls_back_to_event_address_when_no_instances(self):
        """When the selected contract has no instances configured, fall back to event.address."""
        alchemist = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        myt = _contract_node("myt1", "MYT", events=[], read_fns=[self.READ_FN])
        myt["data"]["instances"] = []  # strip instances
        cr = _contractread_node("cr1", contract_node_id="myt1")
        entity = _entity_node("e1", "DepositRecord", fields=[
            {"name": "id",      "type": "ID",     "required": True},
            {"name": "balance", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "evt"),
            _edge("ev2", "c1", "implicit-tx-hash", "e1", "field-id"),
            _edge("ev3", "c1", "event-Deposit-sender", "cr1", "in-account"),
            _edge("ev4", "cr1", "out-balance", "e1", "field-balance"),
        ]
        src = compile_graph(_make_config([alchemist, myt, cr, entity], edges))["Alchemist"]
        assert "MYT.bind(event.address)" in src

    def test_bind_uses_wired_address_when_provided(self):
        """Explicit bind-address wire overrides the instance-address default."""
        result = compile_graph(self._base_config(wire_bind_address=True))
        src = result["Alchemist"]
        # implicit-address resolves to event.address; that wired value takes priority
        assert "MYT.bind(" in src
        assert "event.address" in src  # implicit-address resolves to event.address

    def test_function_call_emitted(self):
        """The try_balanceOf call must appear in the output (try_ variant is always used)."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        assert ".try_balanceOf(" in src

    def test_argument_wired_from_event_param(self):
        """The sender address from the event must be passed as the balanceOf argument."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        assert "event.params.sender" in src

    def test_result_assigned_to_entity_field(self):
        """The balanceOf result must be assigned to the entity's balance field."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        # The result variable is assigned to the field
        assert "depositRecordEntity.balance = " in src

    def test_no_bind_for_second_call_in_same_handler(self):
        """The bind() call is emitted only once per node per handler (deduped)."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        # bind appears once
        assert src.count("MYT.bind(") == 1

    def test_revert_safe_pattern_emitted(self):
        """try_ call + reverted check must be emitted so on-chain reverts don't abort handler."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        assert ".try_balanceOf(" in src
        assert ".reverted ?" in src
        # Direct (non-try) call must NOT appear
        assert ".balanceOf(" not in src.replace(".try_balanceOf(", "")

    def test_wired_bind_address_from_different_source(self):
        """Wire a non-implicit address (e.g. event param) into bind-address."""
        alchemist = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        myt = _contract_node("myt1", "MYT", events=[], read_fns=[self.READ_FN])
        cr = _contractread_node("cr1", contract_node_id="myt1")
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id",      "type": "ID",     "required": True},
            {"name": "balance", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "evt"),
            _edge("ev2", "c1", "implicit-tx-hash", "e1", "field-id"),
            # Wire the depositor's address as the bind address
            _edge("ev3", "c1", "event-Deposit-sender", "cr1", "bind-address"),
            _edge("ev4", "c1", "event-Deposit-sender", "cr1", "in-account"),
            _edge("ev5", "cr1", "out-balance", "e1", "field-balance"),
        ]
        result = compile_graph(_make_config([alchemist, myt, cr, entity], edges))
        src = result["Alchemist"]
        # The bind must use event.params.sender, not event.address
        assert "MYT.bind(event.params.sender)" in src

    def test_instance_address_used_as_bind_address(self):
        """
        Wire MYT's implicit-instance-address into bind-address — the compiler
        must emit Address.fromString("0x...") with MYT's configured address.
        The argument (account) is Contract A's address (implicit-address).
        This is the correct pattern for: on Alchemist Deposit, read MYT.balanceOf(alchemistAddress).
        """
        MYT_ADDR = "0xMYTTokenAddress123"
        alchemist = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        myt = {
            "id": "myt1",
            "type": "contract",
            "position": {"x": 0, "y": 200},
            "data": {
                "name": "MYT",
                "abi": [],
                "events": [],
                "readFunctions": [self.READ_FN],
                "instances": [{"label": "main", "address": MYT_ADDR, "startBlock": 1}],
            },
        }
        cr = _contractread_node("cr1", contract_node_id="myt1")
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id",      "type": "ID",     "required": True},
            {"name": "balance", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "evt"),
            _edge("ev2", "c1", "implicit-tx-hash", "e1", "field-id"),
            # Bind to MYT's configured deployed address
            _edge("ev3", "myt1", "implicit-instance-address", "cr1", "bind-address"),
            # Pass Alchemist's address (event.address) as the balanceOf argument
            _edge("ev4", "c1", "implicit-address", "cr1", "in-account"),
            _edge("ev5", "cr1", "out-balance", "e1", "field-balance"),
        ]
        result = compile_graph(_make_config([alchemist, myt, cr, entity], edges))
        src = result["Alchemist"]
        assert f'Address.fromString("{MYT_ADDR}")' in src
        assert f'MYT.bind(Address.fromString("{MYT_ADDR}"))' in src
        assert "event.address" in src  # implicit-address for the account arg


# ── Aggregate entity compilation ───────────────────────────────────────────────

def _aggregate_node(node_id, name, fields=None):
    return {
        "id": node_id,
        "type": "aggregateentity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
        },
    }


class TestAggregateEntityCompilation:
    """Test that aggregateentity nodes compile to correct AssemblyScript."""

    def _agg_config(self, extra_fields=None, wire_field_in=True):
        """Helper that creates an Alchemist contract + AlchemistTVL aggregate entity."""
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        fields = [
            {"name": "id",         "type": "ID",     "required": True},
            {"name": "netBalance", "type": "BigInt",  "required": False},
        ]
        if extra_fields:
            fields.extend(extra_fields)

        contract = _contract_node("c1", "Alchemist", events=[deposit_event])
        agg = _aggregate_node("agg1", "AlchemistTVL", fields=fields)

        edges = [
            _edge("e1", "c1", "event-Deposit", "agg1", "field-id"),
        ]
        if wire_field_in:
            edges.append(
                _edge("e2", "c1", "event-Deposit-amount", "agg1", "field-in-netBalance")
            )
        return _make_config([contract, agg], edges)

    def test_load_or_create_emitted(self):
        result = compile_graph(self._agg_config())
        src = result["Alchemist"]
        assert "AlchemistTVL.load(" in src
        assert "new AlchemistTVL(" in src

    def test_bigint_zero_init(self):
        result = compile_graph(self._agg_config())
        src = result["Alchemist"]
        assert "BigInt.fromI32(0)" in src

    def test_bigdecimal_zero_init(self):
        fields = [{"name": "rate", "type": "BigDecimal", "required": False}]
        result = compile_graph(self._agg_config(extra_fields=fields))
        src = result["Alchemist"]
        assert "BigDecimal.fromString('0')" in src

    def test_string_zero_init(self):
        fields = [{"name": "label", "type": "String", "required": False}]
        result = compile_graph(self._agg_config(extra_fields=fields))
        src = result["Alchemist"]
        assert '""' in src

    def test_id_zero_init(self):
        fields = [{"name": "key", "type": "ID", "required": False}]
        result = compile_graph(self._agg_config(extra_fields=fields))
        src = result["Alchemist"]
        assert '""' in src

    def test_prev_capture_line_emitted(self):
        result = compile_graph(self._agg_config())
        src = result["Alchemist"]
        assert "alchemistTVLEntity_prev_netBalance = alchemistTVLEntity.netBalance" in src

    def test_field_in_wiring_produces_assignment(self):
        result = compile_graph(self._agg_config(wire_field_in=True))
        src = result["Alchemist"]
        # The new value (event.params.amount) should be assigned to netBalance
        assert "alchemistTVLEntity.netBalance = " in src
        assert "event.params.amount" in src

    def test_aggregate_block_before_regular_entity(self):
        """Aggregate entity block must appear before regular entity in same handler."""
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", "Alchemist", events=[deposit_event])
        agg = _aggregate_node("agg1", "AlchemistTVL", fields=[
            {"name": "id",         "type": "ID",     "required": True},
            {"name": "netBalance", "type": "BigInt",  "required": False},
        ])
        entity = _entity_node("e1", "DepositEvent", fields=[
            {"name": "id",     "type": "ID",    "required": True},
            {"name": "amount", "type": "BigInt", "required": False},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "agg1", "field-id"),
            _edge("e2", "c1", "event-Deposit-amount", "agg1", "field-in-netBalance"),
            _edge("e3", "c1", "event-Deposit", "e1", "field-id"),
            _edge("e4", "c1", "event-Deposit-amount", "e1", "field-amount"),
        ]
        result = compile_graph(_make_config([contract, agg, entity], edges))
        src = result["Alchemist"]
        agg_pos = src.index("AlchemistTVL.load(")
        entity_pos = src.index("DepositEvent.load(")
        assert agg_pos < entity_pos, "Aggregate block should appear before regular entity block"


# ── Aggregate prev port ────────────────────────────────────────────────────────

class TestAggregatePrevPort:
    """Test that field-prev-{name} source handle on aggregateentity resolves to {var}_prev_{name}."""

    def test_prev_port_wired_to_math(self):
        """Wire aggregate prev value into a math node, verify the prev variable name appears."""
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", "Alchemist", events=[deposit_event])
        agg = _aggregate_node("agg1", "AlchemistTVL", fields=[
            {"name": "id",         "type": "ID",     "required": True},
            {"name": "netBalance", "type": "BigInt",  "required": False},
        ])
        math = _math_node("m1", operation="add")
        # History entity records the delta
        history = _entity_node("h1", "DepositHistory", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "delta", "type": "BigInt",  "required": False},
        ])
        edges = [
            # Wire aggregate
            _edge("ea1", "c1", "event-Deposit", "agg1", "field-id"),
            _edge("ea2", "c1", "event-Deposit-amount", "agg1", "field-in-netBalance"),
            # Wire history entity
            _edge("eh1", "c1", "event-Deposit", "h1", "field-id"),
            # math: prev + amount → delta
            _edge("em1", "agg1", "field-prev-netBalance", "m1", "left"),
            _edge("em2", "c1", "event-Deposit-amount", "m1", "right"),
            _edge("em3", "m1", "result", "h1", "field-delta"),
        ]
        result = compile_graph(_make_config([contract, agg, math, history], edges))
        src = result["Alchemist"]
        # The prev variable must appear in the compiled output
        assert "alchemistTVLEntity_prev_netBalance" in src

    def test_prev_port_wired_to_entity_field(self):
        """Wire aggregate prev value directly to a regular entity field."""
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", "Vault", events=[deposit_event])
        agg = _aggregate_node("agg1", "VaultTVL", fields=[
            {"name": "id",      "type": "ID",     "required": True},
            {"name": "balance", "type": "BigInt",  "required": False},
        ])
        snapshot = _entity_node("s1", "Snapshot", fields=[
            {"name": "id",          "type": "ID",     "required": True},
            {"name": "prevBalance", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ea1", "c1", "event-Deposit", "agg1", "field-id"),
            _edge("ea2", "c1", "event-Deposit-amount", "agg1", "field-in-balance"),
            _edge("es1", "c1", "event-Deposit", "s1", "field-id"),
            _edge("es2", "agg1", "field-prev-balance", "s1", "field-prevBalance"),
        ]
        result = compile_graph(_make_config([contract, agg, snapshot], edges))
        src = result["Vault"]
        assert "vaultTVLEntity_prev_balance" in src


# ── field-out-id port ─────────────────────────────────────────────────────────

class TestFieldOutId:
    """Test that field-out-id on an aggregateentity resolves to {var}Id variable."""

    def _base_config(self):
        """AlchemistTVL aggregate + AlchemistTVLHistory entity, linked by field-out-id."""
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", "Alchemist", events=[deposit_event])
        agg = _aggregate_node("agg1", "AlchemistTVL", fields=[
            {"name": "id",         "type": "ID",     "required": True},
            {"name": "netBalance", "type": "BigInt",  "required": False},
        ])
        history = _entity_node("h1", "AlchemistTVLHistory", fields=[
            {"name": "id",  "type": "ID",            "required": True},
            {"name": "tvl", "type": "AlchemistTVL",  "required": False},
        ])
        edges = [
            # Aggregate wiring
            _edge("ea1", "c1", "event-Deposit", "agg1", "evt"),
            _edge("ea2", "c1", "implicit-address", "agg1", "field-id"),
            _edge("ea3", "c1", "event-Deposit-amount", "agg1", "field-in-netBalance"),
            # History entity
            _edge("eh1", "c1", "event-Deposit", "h1", "evt"),
            _edge("eh2", "c1", "implicit-tx-hash", "h1", "field-id"),
            _edge("eh3", "agg1", "field-out-id", "h1", "field-tvl"),
        ]
        return _make_config([contract, agg, history], edges)

    def test_named_id_variable_declared(self):
        """The aggregate's id value must be stored in a named let before load()."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        # The named id variable should appear before the load() call
        assert "alchemistTVLEntityId" in src

    def test_named_id_variable_before_load(self):
        """let alchemistTVLEntityId = ... must come before AlchemistTVL.load(...)."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        id_var_pos = src.index("alchemistTVLEntityId")
        load_pos = src.index("AlchemistTVL.load(")
        assert id_var_pos < load_pos

    def test_field_out_id_resolves_to_id_var(self):
        """field-out-id on the aggregate must resolve to the alchemistTVLEntityId variable."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        # The history entity's tvl field should be assigned the id variable
        assert "alchemistTVLHistoryEntity.tvl = alchemistTVLEntityId" in src

    def test_field_out_id_used_as_entity_reference(self):
        """field-out-id should not generate an 'undefined handle' comment."""
        result = compile_graph(self._base_config())
        src = result["Alchemist"]
        assert "/* aggregateentity" not in src


# ── @derivedFrom fields ───────────────────────────────────────────────────────

class TestDerivedFromFields:
    """Test that fields with derivedFrom set are skipped during entity compilation."""

    def _entity_with_derived(self, derived_value="activity"):
        """Create an entity where one field has @derivedFrom set."""
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", "Vault", events=[deposit_event])
        entity = _entity_node("e1", "VaultTVL", fields=[
            {"name": "id",       "type": "ID",              "required": True},
            {"name": "balance",  "type": "BigInt",           "required": False},
            # Virtual reverse relation — should be skipped by compiler
            {"name": "history",  "type": "VaultTVLHistory", "required": False,
             "derivedFrom": derived_value},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "e1", "evt"),
            _edge("e2", "c1", "event-Deposit-amount", "e1", "field-balance"),
        ]
        return _make_config([contract, entity], edges)

    def test_derived_from_field_not_assigned(self):
        """A field with derivedFrom must not appear as an assignment in the output."""
        result = compile_graph(self._entity_with_derived("activity"))
        src = result["Vault"]
        # The virtual field name must not appear on the left-hand side of an assignment
        assert "vaultTVLEntity.history" not in src

    def test_derived_from_field_skipped_entirely(self):
        """The @derivedFrom field name should not appear anywhere in the handler body."""
        result = compile_graph(self._entity_with_derived("activity"))
        src = result["Vault"]
        # The field name "history" must not appear in any assignment context
        lines_with_history = [
            line for line in src.splitlines()
            if "vaultTVLEntity.history" in line
        ]
        assert lines_with_history == []

    def test_non_derived_fields_still_compiled(self):
        """Normal fields alongside a derivedFrom field must still be compiled."""
        result = compile_graph(self._entity_with_derived("activity"))
        src = result["Vault"]
        assert "vaultTVLEntity.balance = " in src

    def test_empty_string_derived_from_also_skipped(self):
        """An empty derivedFrom string (toggled on but field name not yet typed) is still skipped."""
        result = compile_graph(self._entity_with_derived(""))
        src = result["Vault"]
        assert "vaultTVLEntity.history" not in src


# ── Full TVL + History pattern ────────────────────────────────────────────────

class TestTVLHistoryPattern:
    """
    Integration test for the Alchemix-style pattern:
      - AlchemistTVL aggregate (running balance, updated on Deposit)
      - AlchemistTVLHistory entity (one row per Deposit, linked to the TVL record)
      - AlchemistTVL.activity is a @derivedFrom virtual field pointing back at history rows
    """

    def _make_full_config(self):
        deposit_event = {
            "name": "Deposit",
            "signature": "Deposit(address,uint256)",
            "params": [
                {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
                {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
            ],
        }
        contract = _contract_node("c1", "Alchemist", events=[deposit_event])

        # Running balance aggregate
        tvl = _aggregate_node("tvl1", "AlchemistTVL", fields=[
            {"name": "id",         "type": "ID",     "required": True},
            {"name": "netBalance", "type": "BigInt",  "required": False},
            # Virtual reverse relation — must be skipped by compiler
            {
                "name": "activity",
                "type": "AlchemistTVLHistory",
                "required": False,
                "derivedFrom": "tvl",
            },
        ])

        # History entity
        math = _math_node("m1", operation="add")
        history = _entity_node("h1", "AlchemistTVLHistory", fields=[
            {"name": "id",         "type": "ID",            "required": True},
            {"name": "tvl",        "type": "AlchemistTVL",  "required": False},
            {"name": "netBalance", "type": "BigInt",         "required": False},
        ])

        edges = [
            # TVL aggregate
            _edge("e1",  "c1",   "event-Deposit",            "tvl1", "evt"),
            _edge("e2",  "c1",   "implicit-address",          "tvl1", "field-id"),
            _edge("e3",  "tvl1", "field-prev-netBalance",     "m1",   "left"),
            _edge("e4",  "c1",   "event-Deposit-amount",      "m1",   "right"),
            _edge("e5",  "m1",   "result",                    "tvl1", "field-in-netBalance"),
            # History entity
            _edge("e6",  "c1",   "event-Deposit",             "h1",   "evt"),
            _edge("e7",  "c1",   "implicit-tx-hash",          "h1",   "field-id"),
            _edge("e8",  "tvl1", "field-out-id",              "h1",   "field-tvl"),
            _edge("e9",  "c1",   "event-Deposit-amount",      "h1",   "field-netBalance"),
        ]
        return _make_config([contract, tvl, math, history], edges)

    def test_tvl_aggregate_compiled(self):
        result = compile_graph(self._make_full_config())
        src = result["Alchemist"]
        assert "AlchemistTVL.load(" in src
        assert "new AlchemistTVL(" in src

    def test_history_entity_compiled(self):
        result = compile_graph(self._make_full_config())
        src = result["Alchemist"]
        assert "AlchemistTVLHistory.load(" in src or "new AlchemistTVLHistory(" in src

    def test_math_add_in_output(self):
        result = compile_graph(self._make_full_config())
        src = result["Alchemist"]
        assert ".plus(" in src

    def test_history_tvl_field_uses_id_var(self):
        """The history entity's tvl field must be assigned the alchemistTVLId variable."""
        result = compile_graph(self._make_full_config())
        src = result["Alchemist"]
        assert "alchemistTVLHistoryEntity.tvl = alchemistTVLEntityId" in src

    def test_derived_from_activity_not_assigned(self):
        """The @derivedFrom 'activity' field on the aggregate must not be assigned."""
        result = compile_graph(self._make_full_config())
        src = result["Alchemist"]
        assert "alchemistTVLEntity.activity" not in src

    def test_aggregate_block_before_history_block(self):
        """The TVL aggregate block must appear before the history entity block in the handler."""
        result = compile_graph(self._make_full_config())
        src = result["Alchemist"]
        tvl_pos = src.index("AlchemistTVL.load(")
        # Use the history entity's load/new call, not its appearance in imports
        history_pos = src.index("AlchemistTVLHistory.load(")
        assert tvl_pos < history_pos


# ── triggerEvents checklist ───────────────────────────────────────────────────

def _aggregate_node_with_triggers(node_id, name, fields, trigger_events):
    """Build an aggregateentity node with a triggerEvents checklist."""
    return {
        "id": node_id,
        "type": "aggregateentity",
        "position": {"x": 400, "y": 0},
        "data": {
            "name": name,
            "fields": fields,
            "triggerEvents": trigger_events,
        },
    }


class TestTriggerEvents:
    """Aggregate entity fired via triggerEvents checklist (no direct evt edge)."""

    DEPOSIT_EVENT = {
        "name": "Deposit",
        "signature": "Deposit(address,uint256)",
        "params": [
            {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
            {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
        ],
    }

    WITHDRAW_EVENT = {
        "name": "Withdraw",
        "signature": "Withdraw(address,uint256)",
        "params": [
            {"name": "recipient", "solidity_type": "address", "graph_type": "Address"},
            {"name": "amount",    "solidity_type": "uint256",  "graph_type": "BigInt"},
        ],
    }

    def _single_trigger_config(self):
        """Aggregate triggered by Deposit via triggerEvents only (no evt edge).
        The field-in wire comes from the Deposit event param.
        """
        contract = _contract_node("c1", "Vault", events=[self.DEPOSIT_EVENT])
        agg = _aggregate_node_with_triggers(
            "agg1", "VaultTVL",
            fields=[
                {"name": "id",      "type": "ID",     "required": True},
                {"name": "balance", "type": "BigInt",  "required": False},
            ],
            trigger_events=[
                {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"},
            ],
        )
        edges = [
            # id is wired (required), but no direct "evt" edge — trigger is via checklist
            _edge("e1", "c1", "implicit-address", "agg1", "field-id"),
            _edge("e2", "c1", "event-Deposit-amount", "agg1", "field-in-balance"),
        ]
        return _make_config([contract, agg], edges)

    def test_trigger_events_handler_generated(self):
        """A handler is generated even when the aggregate has no direct evt edge."""
        result = compile_graph(self._single_trigger_config())
        assert "handleDeposit" in result["Vault"]

    def test_trigger_events_aggregate_load_emitted(self):
        """The aggregate's load-or-create block is present in the handler."""
        result = compile_graph(self._single_trigger_config())
        src = result["Vault"]
        assert "VaultTVL.load(" in src
        assert "new VaultTVL(" in src

    def test_trigger_events_field_in_written(self):
        """The field-in wire from the triggering event's params is written."""
        result = compile_graph(self._single_trigger_config())
        src = result["Vault"]
        assert "vaultTVLEntity.balance = " in src
        assert "event.params.amount" in src

    def test_trigger_events_zero_init(self):
        """Zero initialisation block is emitted for load-or-create."""
        result = compile_graph(self._single_trigger_config())
        src = result["Vault"]
        assert "BigInt.fromI32(0)" in src

    def _multi_trigger_config(self):
        """Aggregate triggered by BOTH Deposit and Withdraw via triggerEvents.
        Each event provides its own field-in wire.
        """
        contract = _contract_node(
            "c1", "Vault", events=[self.DEPOSIT_EVENT, self.WITHDRAW_EVENT]
        )
        agg = _aggregate_node_with_triggers(
            "agg1", "VaultTVL",
            fields=[
                {"name": "id",         "type": "ID",     "required": True},
                {"name": "netBalance", "type": "BigInt",  "required": False},
            ],
            trigger_events=[
                {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"},
                {"contractId": "c1", "contractName": "Vault", "eventName": "Withdraw"},
            ],
        )
        edges = [
            # Stable ID from the contract address (same for both events)
            _edge("e1", "c1", "implicit-address", "agg1", "field-id"),
            # Deposit wires its own amount into netBalance
            _edge("e2", "c1", "event-Deposit-amount", "agg1", "field-in-netBalance"),
        ]
        return _make_config([contract, agg], edges)

    def test_multi_trigger_deposit_handler_generated(self):
        """A Deposit handler is generated for the multi-trigger aggregate."""
        result = compile_graph(self._multi_trigger_config())
        assert "handleDeposit" in result["Vault"]

    def test_multi_trigger_withdraw_handler_generated(self):
        """A Withdraw handler is also generated for the multi-trigger aggregate."""
        result = compile_graph(self._multi_trigger_config())
        assert "handleWithdraw" in result["Vault"]

    def test_multi_trigger_deposit_writes_field(self):
        """Deposit handler writes the netBalance from event.params.amount."""
        result = compile_graph(self._multi_trigger_config())
        src = result["Vault"]
        # Deposit is the event that supplies the field-in wire
        # Find just the handleDeposit function body
        assert "handleDeposit" in src
        # The deposit amount wire should be present somewhere in the output
        assert "event.params.amount" in src

    def test_multi_trigger_withdraw_does_not_write_deposit_param(self):
        """Withdraw handler must NOT reference event.params.amount from Deposit.

        The field-in-netBalance wire comes from event-Deposit-amount, which is
        not valid in the Withdraw handler context.  The compiler must skip that
        field write in the Withdraw handler, leaving the aggregate's existing
        netBalance value unchanged.
        """
        result = compile_graph(self._multi_trigger_config())
        src = result["Vault"]
        # Split on function boundaries to inspect only the Withdraw handler
        withdraw_start = src.find("export function handleWithdraw(")
        assert withdraw_start != -1, "handleWithdraw must exist"
        withdraw_body = src[withdraw_start:]
        # The deposit-specific param must not appear in the Withdraw handler
        assert "event.params.amount" not in withdraw_body

    def test_multi_trigger_withdraw_still_loads_and_saves(self):
        """Even when no field is written, the Withdraw handler still loads and saves."""
        result = compile_graph(self._multi_trigger_config())
        src = result["Vault"]
        withdraw_start = src.find("export function handleWithdraw(")
        assert withdraw_start != -1
        withdraw_body = src[withdraw_start:]
        assert "VaultTVL.load(" in withdraw_body
        assert ".save()" in withdraw_body

    def test_multi_trigger_withdraw_has_prev_captures(self):
        """Withdraw handler must still capture prev values (needed for downstream wires)."""
        result = compile_graph(self._multi_trigger_config())
        src = result["Vault"]
        withdraw_start = src.find("export function handleWithdraw(")
        withdraw_body = src[withdraw_start:]
        assert "vaultTVLEntity_prev_netBalance" in withdraw_body


class TestContractReadAutoBindInstanceEmpty:
    """Edge cases for auto-bind when instances list is empty."""

    DEPOSIT_EVENT = {
        "name": "Deposit",
        "signature": "Deposit(address,uint256)",
        "params": [
            {"name": "sender", "solidity_type": "address", "graph_type": "Address"},
            {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
        ],
    }

    READ_FN = {
        "name": "totalSupply",
        "signature": "totalSupply()",
        "inputs":  [],
        "outputs": [{"name": "supply", "solidity_type": "uint256", "graph_type": "BigInt"}],
    }

    def test_empty_instances_falls_back_to_event_address(self):
        """When selected contract has no instances, bind falls back to event.address."""
        alchemist = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        token = _contract_node("t1", "Token", events=[], read_fns=[self.READ_FN])
        token["data"]["instances"] = []  # explicitly empty
        cr = {
            "id": "cr1",
            "type": "contractread",
            "position": {"x": 600, "y": 0},
            "data": {"contractNodeId": "t1", "fnIndex": 0},
        }
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "supply", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "evt"),
            _edge("ev2", "c1", "implicit-tx-hash", "e1", "field-id"),
            _edge("ev3", "cr1", "out-supply", "e1", "field-supply"),
        ]
        src = compile_graph(_make_config([alchemist, token, cr, entity], edges))["Alchemist"]
        assert "Token.bind(event.address)" in src

    def test_instances_key_missing_falls_back_to_event_address(self):
        """When the instances key is absent entirely, bind falls back to event.address."""
        alchemist = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        token = _contract_node("t1", "Token", events=[], read_fns=[self.READ_FN])
        del token["data"]["instances"]  # remove the key entirely
        cr = {
            "id": "cr1",
            "type": "contractread",
            "position": {"x": 600, "y": 0},
            "data": {"contractNodeId": "t1", "fnIndex": 0},
        }
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "supply", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "evt"),
            _edge("ev2", "c1", "implicit-tx-hash", "e1", "field-id"),
            _edge("ev3", "cr1", "out-supply", "e1", "field-supply"),
        ]
        src = compile_graph(_make_config([alchemist, token, cr, entity], edges))["Alchemist"]
        assert "Token.bind(event.address)" in src

    def test_no_spurious_address_import_line(self):
        """Auto-bind must not emit a bare 'Address' string as an import line."""
        alchemist = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        token = _contract_node("t1", "Token", events=[], read_fns=[self.READ_FN])
        # Token has a valid instance — will use Address.fromString(...)
        cr = {
            "id": "cr1",
            "type": "contractread",
            "position": {"x": 600, "y": 0},
            "data": {"contractNodeId": "t1", "fnIndex": 0},
        }
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "supply", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "evt"),
            _edge("ev2", "c1", "implicit-tx-hash", "e1", "field-id"),
            _edge("ev3", "cr1", "out-supply", "e1", "field-supply"),
        ]
        src = compile_graph(_make_config([alchemist, token, cr, entity], edges))["Alchemist"]
        # There must be no line that is just "Address" (the bare import bug)
        lines = src.splitlines()
        assert "Address" not in lines, (
            "Found bare 'Address' string as a standalone line — spurious import bug"
        )


# ── Helper for aggregate entity (mirrors simulator helper) ────────────────────

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


# ── Entity triggerEvents (no-wire multi-trigger for regular entity) ────────────

class TestEntityTriggerEvents:
    """Regular entity nodes can declare triggerEvents to fire without a direct
    evt wire — same mechanism as AggregateEntity."""

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

    def test_entity_trigger_events_generates_handler(self):
        """Entity with triggerEvents produces a handler even without a direct wire."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}
        ])
        result = compile_graph(_make_config([contract, entity], []))
        assert "Vault" in result
        assert "handleDeposit" in result["Vault"]

    def test_entity_trigger_events_default_id_expression(self):
        """When no field-id wire exists, entity uses tx.hash as default ID."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"}
        ])
        src = compile_graph(_make_config([contract, entity], []))["Vault"]
        assert "toHexString()" in src

    def test_entity_triggered_by_multiple_events(self):
        """Entity with two triggerEvents generates two separate handlers."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT, WITHDRAW_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "Deposit"},
            {"contractId": "c1", "contractName": "Vault", "eventName": "Withdraw"},
        ])
        src = compile_graph(_make_config([contract, entity], []))["Vault"]
        assert "handleDeposit" in src
        assert "handleWithdraw" in src

    def test_entity_trigger_wrong_event_name_skipped(self):
        """triggerEvent for a non-existent event on the contract produces no handler."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "c1", "contractName": "Vault", "eventName": "NonExistent"}
        ])
        result = compile_graph(_make_config([contract, entity], []))
        assert "handleNonExistent" not in result.get("Vault", "")

    def test_entity_trigger_wrong_contract_id_skipped(self):
        """triggerEvent pointing to a different contractId is ignored."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = self._entity_with_trigger([
            {"contractId": "other-contract", "contractName": "Vault", "eventName": "Deposit"}
        ])
        result = compile_graph(_make_config([contract, entity], []))
        # The Deposit event exists but no entity is wired/triggered → no handler
        assert "handleDeposit" not in result.get("Vault", "")

    def test_entity_trigger_and_direct_wire_both_work(self):
        """An entity can be wired directly AND appear in triggerEvents simultaneously."""
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
        edges = [
            # Direct wire for Deposit
            _edge("ev1", "c1", "event-Deposit", "e1", "field-id"),
        ]
        src = compile_graph(_make_config([contract, entity], edges))["Vault"]
        assert "handleDeposit" in src
        assert "handleWithdraw" in src


# ── Edge cases: empty/missing names ───────────────────────────────────────────

class TestEdgeCases:
    def test_event_with_empty_name_skipped(self):
        """An event whose name is empty string must be silently skipped."""
        bad_event = {"name": "", "signature": "()", "params": []}
        contract = _contract_node("c1", "Vault", events=[bad_event, DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id", "type": "ID", "required": True}
        ])
        edges = [_edge("ev1", "c1", "event-Deposit", "e1", "field-id")]
        # Must not raise; empty-name event skipped; Deposit handler still works
        result = compile_graph(_make_config([contract, entity], edges))
        assert "handleDeposit" in result["Vault"]
        assert "handleUnknownEvent" not in result.get("Vault", "")

    def test_event_missing_name_key_skipped(self):
        """An event dict without a 'name' key must not crash."""
        bad_event = {"signature": "()", "params": []}
        contract = _contract_node("c1", "Vault", events=[bad_event, DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id", "type": "ID", "required": True}
        ])
        edges = [_edge("ev1", "c1", "event-Deposit", "e1", "field-id")]
        result = compile_graph(_make_config([contract, entity], edges))
        assert "handleDeposit" in result["Vault"]

    def test_entity_with_empty_name_uses_unknown_fallback(self):
        """Entity with empty name must not crash — falls back to UnknownEntity."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "", fields=[
            {"name": "id", "type": "ID", "required": True}
        ])
        edges = [_edge("ev1", "c1", "event-Deposit", "e1", "field-id")]
        # Must not raise IndexError
        result = compile_graph(_make_config([contract, entity], edges))
        assert "Vault" in result
        src = result["Vault"]
        assert "UnknownEntity" in src

    def test_handler_name_helper_with_normal_name(self):
        """_handler_name produces expected PascalCase result for standard names."""
        from subgraph_wizard.generate.graph_compiler import _handler_name
        assert _handler_name("Transfer") == "handleTransfer"
        assert _handler_name("deposit") == "handleDeposit"
        assert _handler_name("Swap") == "handleSwap"

    def test_handler_name_helper_with_empty_string(self):
        """_handler_name does not crash on empty string."""
        from subgraph_wizard.generate.graph_compiler import _handler_name
        result = _handler_name("")
        assert "handle" in result.lower()

    def test_field_with_empty_name_skipped(self):
        """Fields with empty names are silently skipped — no crash, no bad code."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id",  "type": "ID",    "required": True},
            {"name": "",    "type": "BigInt", "required": False},  # empty name
            {"name": "val", "type": "BigInt", "required": False},
        ])
        edges = [_edge("ev1", "c1", "event-Deposit", "e1", "field-id")]
        result = compile_graph(_make_config([contract, entity], edges))
        src = result["Vault"]
        assert "handleDeposit" in src
        # No bare assignment to an empty field name
        assert "entity. =" not in src
        assert "record. =" not in src


# ── Field order preservation (drag-to-reorder) ────────────────────────────────

class TestFieldOrder:
    """Compiler must emit fields in the order they appear in the node data,
    allowing drag-to-reorder to affect the generated code layout."""

    def test_field_assignment_order_matches_declaration(self):
        """Fields are written in declaration order, not alphabetical."""
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT])
        entity = {
            "id": "e1",
            "type": "entity",
            "position": {"x": 400, "y": 0},
            "data": {
                "name": "Record",
                "fields": [
                    {"name": "id",     "type": "ID",    "required": True},
                    {"name": "zebra",  "type": "BigInt", "required": False},
                    {"name": "alpha",  "type": "BigInt", "required": False},
                ],
            },
        }
        edges = [
            _edge("ev1", "c1", "event-Deposit", "e1", "field-id"),
            _edge("ev2", "c1", "event-Deposit-amount", "e1", "field-zebra"),
            _edge("ev3", "c1", "event-Deposit-amount", "e1", "field-alpha"),
        ]
        src = compile_graph(_make_config([contract, entity], edges))["Vault"]
        # zebra must appear before alpha in the generated source
        idx_zebra = src.find(".zebra")
        idx_alpha = src.find(".alpha")
        assert idx_zebra != -1 and idx_alpha != -1
        assert idx_zebra < idx_alpha, "Fields must appear in declaration order"


# ── Trigger port as value source (Bug: event_param_expr fallback) ─────────────

class TestTriggerPortFallback:
    """When the trigger port (e.g. 'event-Deposit') is wired as a value source
    rather than a param port, the compiler must produce valid AssemblyScript —
    not the invalid 'event.params.event-Deposit' expression."""

    DEPOSIT_EVENT = {
        "name": "Deposit",
        "signature": "Deposit(address,uint256)",
        "params": [
            {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
        ],
    }

    def test_trigger_port_as_field_id_produces_valid_expr(self):
        """Wiring the trigger port to field-id must not emit 'event.params.event-Deposit'."""
        contract = _contract_node("c1", "Vault", events=[self.DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id", "type": "ID", "required": True},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "e1", "field-id"),  # trigger port as id source
        ]
        src = compile_graph(_make_config([contract, entity], edges))["Vault"]
        assert "event.params.event-Deposit" not in src, (
            "Trigger port wired to field-id must not produce invalid expression"
        )

    def test_trigger_port_as_aggregate_field_id_produces_valid_expr(self):
        """Same check for aggregate entity."""
        contract = _contract_node("c1", "Vault", events=[self.DEPOSIT_EVENT])
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
            },
        }
        edges = [
            _edge("e1", "c1", "event-Deposit", "agg1", "field-id"),
            _edge("e2", "c1", "event-Deposit-amount", "agg1", "field-in-balance"),
        ]
        src = compile_graph(_make_config([contract, agg], edges))["Vault"]
        assert "event.params.event-Deposit" not in src

    def test_trigger_port_fallback_uses_tx_hash(self):
        """The fallback expression must be the tx hash (a safe unique-per-event id)."""
        contract = _contract_node("c1", "Vault", events=[self.DEPOSIT_EVENT])
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id", "type": "ID", "required": True},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "e1", "field-id"),
        ]
        src = compile_graph(_make_config([contract, entity], edges))["Vault"]
        assert "transaction.hash" in src


# ── Shared declared_vars across entity blocks (Bug: duplicate let declarations) ─

class TestSharedDeclaredVars:
    """Two entity blocks in the same handler that share a transform node (e.g. a
    math node) must only emit one `let` declaration for the shared variable.
    AssemblyScript rejects duplicate `let` declarations in the same scope."""

    DEPOSIT_EVENT = {
        "name": "Deposit",
        "signature": "Deposit(address,uint256)",
        "params": [
            {"name": "amount", "solidity_type": "uint256", "graph_type": "BigInt"},
        ],
    }

    def test_shared_math_node_single_declaration(self):
        """A math node consumed by two entity fields must only produce ONE `let` stmt."""
        contract = _contract_node("c1", "Vault", events=[self.DEPOSIT_EVENT])
        math = _math_node("m1", operation="add")
        entity_a = _entity_node("ea", "RecordA", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "value", "type": "BigInt",  "required": False},
        ])
        entity_b = _entity_node("eb", "RecordB", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "value", "type": "BigInt",  "required": False},
        ])
        # Both entities wire from the SAME math node result
        edges = [
            _edge("e1", "c1", "event-Deposit", "ea", "evt"),
            _edge("e2", "c1", "implicit-tx-hash", "ea", "field-id"),
            _edge("e3", "c1", "event-Deposit-amount", "m1", "left"),
            _edge("e4", "c1", "event-Deposit-amount", "m1", "right"),
            _edge("e5", "m1", "result", "ea", "field-value"),
            _edge("e6", "c1", "event-Deposit", "eb", "evt"),
            _edge("e7", "c1", "implicit-tx-hash", "eb", "field-id"),
            _edge("e8", "m1", "result", "eb", "field-value"),  # same math node!
        ]
        src = compile_graph(_make_config([contract, math, entity_a, entity_b], edges))["Vault"]
        # Count how many times the math result variable is declared with `let`
        math_var = "_m1__result"
        let_count = src.count(f"let {math_var}")
        assert let_count == 1, (
            f"Math result var '{math_var}' declared {let_count} times — "
            "must be declared exactly once to avoid AssemblyScript duplicate-var error"
        )

    def test_shared_contractread_single_bind(self):
        """A contractread node shared by two entity fields must only emit bind() once."""
        READ_FN = {
            "name": "totalSupply",
            "signature": "totalSupply()",
            "inputs": [],
            "outputs": [{"name": "supply", "solidity_type": "uint256", "graph_type": "BigInt"}],
        }
        contract = _contract_node("c1", "Alchemist", events=[self.DEPOSIT_EVENT])
        token = _contract_node("t1", "Token", events=[], read_fns=[READ_FN])
        cr = {
            "id": "cr1",
            "type": "contractread",
            "position": {"x": 600, "y": 0},
            "data": {"contractNodeId": "t1", "fnIndex": 0},
        }
        entity_a = _entity_node("ea", "SnapshotA", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "supply", "type": "BigInt",  "required": False},
        ])
        entity_b = _entity_node("eb", "SnapshotB", fields=[
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "supply", "type": "BigInt",  "required": False},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit", "ea", "evt"),
            _edge("e2", "c1", "implicit-tx-hash", "ea", "field-id"),
            _edge("e3", "cr1", "out-supply", "ea", "field-supply"),
            _edge("e4", "c1", "event-Deposit", "eb", "evt"),
            _edge("e5", "c1", "implicit-tx-hash", "eb", "field-id"),
            _edge("e6", "cr1", "out-supply", "eb", "field-supply"),  # same contractread!
        ]
        src = compile_graph(_make_config([contract, token, cr, entity_a, entity_b], edges))["Alchemist"]
        # bind() must appear exactly once for the shared contractread node
        assert src.count("Token.bind(") == 1, (
            "Token.bind() emitted more than once — shared contractread must only bind once"
        )


# ── Import filtering: only emit imports for events with handlers ──────────────

class TestImportFiltering:
    """Events that have no wired entities must not appear in the import line.
    Unused imports don't cause errors but add noise."""

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

    def test_unwired_event_not_imported(self):
        """Transfer event has no entity wire — must NOT appear in the import."""
        contract = _contract_node("c1", "Token", events=[self.DEPOSIT_EVENT, self.TRANSFER_EVENT])
        entity = _entity_node("e1", "Record", fields=[
            {"name": "id", "type": "ID", "required": True},
        ])
        # Only Deposit is wired; Transfer has no entity
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        src = compile_graph(_make_config([contract, entity], edges))["Token"]
        assert "Transfer as TransferEvent" not in src, (
            "Unwired Transfer event must not be imported"
        )
        assert "Deposit as DepositEvent" in src, "Wired Deposit event must be imported"

    def test_all_wired_events_imported(self):
        """When both events are wired, both appear in imports."""
        contract = _contract_node("c1", "Token", events=[self.DEPOSIT_EVENT, self.TRANSFER_EVENT])
        entity_a = _entity_node("ea", "DepositRecord", fields=[
            {"name": "id", "type": "ID", "required": True},
        ])
        entity_b = _entity_node("eb", "TransferRecord", fields=[
            {"name": "id", "type": "ID", "required": True},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit",  "ea", "field-id"),
            _edge("e2", "c1", "event-Transfer",  "eb", "field-id"),
        ]
        src = compile_graph(_make_config([contract, entity_a, entity_b], edges))["Token"]
        assert "Deposit as DepositEvent" in src
        assert "Transfer as TransferEvent" in src


# ── Auto-fill: unwired fields filled from matching event param names ───────────

DEPOSIT_EVENT_WITH_PARAMS = {
    "name": "Deposit",
    "signature": "Deposit(uint256,uint256)",
    "params": [
        {"name": "amount",      "solidity_type": "uint256", "graph_type": "BigInt"},
        {"name": "recipientId", "solidity_type": "uint256", "graph_type": "BigInt"},
    ],
}


class TestAutoFillFromEventParams:
    """Auto-fill: entity fields with no wire get auto-assigned from event params
    when the field name matches a param name (README feature)."""

    def _config(self, fields, edges):
        contract = _contract_node("c1", "Vault", events=[DEPOSIT_EVENT_WITH_PARAMS])
        entity = _entity_node("e1", "VaultDeposit", fields=fields)
        return _make_config([contract, entity], edges)

    def test_unwired_field_auto_filled_from_param(self):
        """Field 'amount' with no wire → event.params.amount injected."""
        fields = [
            {"name": "id",     "type": "ID",     "required": True},
            {"name": "amount", "type": "BigInt",  "required": True},
        ]
        # Only trigger wire (event-Deposit → entity evt) — no field wire for amount
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        src = compile_graph(self._config(fields, edges))["Vault"]
        assert "event.params.amount" in src

    def test_unwired_field_matching_two_params(self):
        """Both 'amount' and 'recipientId' auto-filled when not wired."""
        fields = [
            {"name": "id",          "type": "ID",    "required": True},
            {"name": "amount",      "type": "BigInt", "required": True},
            {"name": "recipientId", "type": "BigInt", "required": True},
        ]
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        src = compile_graph(self._config(fields, edges))["Vault"]
        assert "event.params.amount" in src
        assert "event.params.recipientId" in src

    def test_explicit_wire_takes_precedence_over_auto_fill(self):
        """An explicit wire overrides auto-fill for the same field."""
        fields = [
            {"name": "id",     "type": "ID",    "required": True},
            {"name": "amount", "type": "BigInt", "required": True},
        ]
        # Wire event-Deposit-recipientId → field-amount (intentional override)
        edges = [
            _edge("e1", "c1", "event-Deposit", "e1", "field-id"),
            _edge("e2", "c1", "event-Deposit-recipientId", "e1", "field-amount"),
        ]
        src = compile_graph(self._config(fields, edges))["Vault"]
        assert "event.params.recipientId" in src
        # auto-fill event.params.amount should NOT appear since field is explicitly wired
        # (the explicit wire provides event.params.recipientId, not event.params.amount)
        lines = [l.strip() for l in src.splitlines() if "amount" in l]
        # Should be only one assignment and it should reference recipientId
        amount_assigns = [l for l in lines if "vaultDepositEntity.amount" in l]
        assert len(amount_assigns) == 1
        assert "recipientId" in amount_assigns[0]

    def test_field_name_not_in_params_not_auto_filled(self):
        """A field whose name has no matching event param stays unassigned."""
        fields = [
            {"name": "id",     "type": "ID",    "required": True},
            {"name": "fooBar", "type": "BigInt", "required": True},
        ]
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        src = compile_graph(self._config(fields, edges))["Vault"]
        assert "event.params.fooBar" not in src

    def test_derived_from_field_not_auto_filled(self):
        """@derivedFrom fields are always skipped (virtual reverse relations)."""
        fields = [
            {"name": "id",     "type": "ID",    "required": True},
            {"name": "amount", "type": "BigInt", "required": True, "derivedFrom": "someField"},
        ]
        edges = [_edge("e1", "c1", "event-Deposit", "e1", "field-id")]
        src = compile_graph(self._config(fields, edges))["Vault"]
        assert "event.params.amount" not in src

    def test_type_mismatch_raises_error(self):
        """Auto-fill raises ValueError when entity field type != event param graph_type.

        Silently skipping a matched-name field with a wrong type produces a null
        field in the deployed subgraph, which is harder to debug than a build error.
        A ValueError is raised immediately so the user knows exactly what to fix.
        """
        batch_event = {
            "name": "BatchLiquidate",
            "signature": "BatchLiquidate(bytes,uint256[])",
            "params": [
                # ABI parser returns graph_type "Bytes" for address[] or bytes
                {"name": "accounts", "solidity_type": "bytes",     "graph_type": "Bytes"},
                {"name": "shares",   "solidity_type": "uint256[]", "graph_type": "[BigInt!]"},
            ],
        }
        contract = _contract_node("c1", "Alchemist", events=[batch_event])
        entity = _entity_node("e1", "BatchLiquidateEvent", fields=[
            {"name": "id",       "type": "ID",        "required": True},
            # Entity field type [BigInt!] — does NOT match param graph_type "Bytes"
            {"name": "accounts", "type": "[BigInt!]",  "required": False},
            # Entity field type [BigInt!] — matches param graph_type "[BigInt!]"
            {"name": "shares",   "type": "[BigInt!]",  "required": False},
        ])
        edges = [_edge("e1", "c1", "event-BatchLiquidate", "e1", "field-id")]
        import pytest
        with pytest.raises(ValueError, match="Auto-fill type mismatch"):
            compile_graph(_make_config([contract, entity], edges))

    def test_type_match_array_auto_fills(self):
        """When entity field and event param are both [BigInt!], auto-fill works."""
        batch_event = {
            "name": "BatchLiquidate",
            "signature": "BatchLiquidate(uint256[])",
            "params": [
                {"name": "shares", "solidity_type": "uint256[]", "graph_type": "[BigInt!]"},
            ],
        }
        contract = _contract_node("c1", "Alchemist", events=[batch_event])
        entity = _entity_node("e1", "BatchLiquidateEvent", fields=[
            {"name": "id",     "type": "ID",       "required": True},
            {"name": "shares", "type": "[BigInt!]", "required": False},
        ])
        edges = [_edge("e1", "c1", "event-BatchLiquidate", "e1", "field-id")]
        src = compile_graph(_make_config([contract, entity], edges))["Alchemist"]
        assert "event.params.shares" in src


# ── implicit-instance-address falls back to Networks panel address ─────────────

class TestImplicitInstanceAddressFallback:
    """implicit-instance-address should resolve to the address from the Networks
    panel config when the ContractNode's inline address field is empty."""

    DEPOSIT_EVENT = {
        "name": "Deposit",
        "signature": "Deposit()",
        "params": [],
    }

    def _contract_node_no_inline_addr(self, node_id, name):
        """Contract node with NO inline address (user only filled Networks tab)."""
        return {
            "id": node_id,
            "type": "contract",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "abi": [],
                "address": "",  # empty — user did not fill inline field
                "events": [self.DEPOSIT_EVENT],
                "readFunctions": [],
            },
        }

    def test_networks_address_used_when_inline_empty(self):
        """When inline address is empty, Networks panel address is used."""
        EXPECTED_ADDR = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"
        networks = [{
            "network": "mainnet",
            "contracts": {
                "Vault": {
                    "instances": [
                        {"label": "main", "address": EXPECTED_ADDR, "startBlock": 1000}
                    ]
                }
            }
        }]
        entity = _entity_node("e1", "VaultRecord", fields=[
            {"name": "id",    "type": "ID",      "required": True},
            {"name": "vault", "type": "Address",  "required": True},
        ])
        contract = self._contract_node_no_inline_addr("c1", "Vault")
        edges = [
            _edge("e1", "c1", "event-Deposit",           "e1", "field-id"),
            _edge("e2", "c1", "implicit-instance-address","e1", "field-vault"),
        ]
        cfg = {
            "schema_version": 1,
            "subgraph_name": "test",
            "networks": networks,
            "nodes": [contract, entity],
            "edges": edges,
        }
        src = compile_graph(cfg)["Vault"]
        assert EXPECTED_ADDR in src, (
            f"Networks-panel address {EXPECTED_ADDR!r} should appear in mapping"
        )
        assert "0x0000000000000000000000000000000000000000" not in src, (
            "Zero address should NOT appear when Networks-panel address is set"
        )

    def test_inline_address_takes_precedence_over_networks(self):
        """When inline address is set, it takes precedence over Networks panel."""
        INLINE_ADDR   = "0x1111111111111111111111111111111111111111"
        NETWORKS_ADDR = "0x2222222222222222222222222222222222222222"
        networks = [{
            "network": "mainnet",
            "contracts": {
                "Vault": {
                    "instances": [
                        {"label": "main", "address": NETWORKS_ADDR, "startBlock": 1}
                    ]
                }
            }
        }]
        contract = {
            "id": "c1",
            "type": "contract",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": "Vault",
                "abi": [],
                "address": INLINE_ADDR,  # inline address IS set
                "events": [self.DEPOSIT_EVENT],
                "readFunctions": [],
            },
        }
        entity = _entity_node("e1", "VaultRecord", fields=[
            {"name": "id",    "type": "ID",     "required": True},
            {"name": "vault", "type": "Address", "required": True},
        ])
        edges = [
            _edge("e1", "c1", "event-Deposit",            "e1", "field-id"),
            _edge("e2", "c1", "implicit-instance-address", "e1", "field-vault"),
        ]
        cfg = {
            "schema_version": 1,
            "subgraph_name": "test",
            "networks": networks,
            "nodes": [contract, entity],
            "edges": edges,
        }
        src = compile_graph(cfg)["Vault"]
        assert INLINE_ADDR in src
        assert NETWORKS_ADDR not in src
