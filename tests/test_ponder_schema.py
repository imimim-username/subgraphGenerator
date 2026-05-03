"""Tests for generate/ponder_schema.py — render_ponder_schema."""

import pytest
from subgraph_wizard.generate.ponder_schema import render_ponder_schema


# ── Config builder helpers ─────────────────────────────────────────────────────

def _cfg(nodes=None, edges=None):
    return {
        "schema_version": 1,
        "subgraph_name": "test",
        "networks": [],
        "nodes": nodes or [],
        "edges": edges or [],
        "ponder_settings": {},
    }


def _entity(node_id, name, fields=None):
    return {
        "id": node_id,
        "type": "entity",
        "position": {"x": 0, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
        },
    }


def _agg(node_id, name, fields=None):
    return {
        "id": node_id,
        "type": "aggregateentity",
        "position": {"x": 0, "y": 0},
        "data": {
            "name": name,
            "fields": fields or [{"name": "id", "type": "ID", "required": True}],
            "triggerEvents": [],
        },
    }


def _field(name, ftype, required=False, derived_from=None):
    f = {"name": name, "type": ftype, "required": required}
    if derived_from:
        f["derivedFrom"] = derived_from
    return f


# ── File structure ────────────────────────────────────────────────────────────

class TestFileStructure:
    def test_empty_config_has_import_only(self):
        out = render_ponder_schema(_cfg())
        assert 'import { onchainTable } from "ponder"' in out
        assert "onchainTable" in out
        assert "export const" not in out

    def test_single_entity_export_emitted(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer")]))
        assert "export const transfer = onchainTable" in out

    def test_non_entity_nodes_ignored(self):
        nodes = [
            {"id": "c1", "type": "contract", "position": {}, "data": {"name": "Token", "fields": []}},
            {"id": "m1", "type": "math", "position": {}, "data": {"operation": "add"}},
            _entity("e1", "Transfer"),
        ]
        out = render_ponder_schema(_cfg(nodes=nodes))
        assert "contract" not in out
        assert "math" not in out
        assert "export const transfer" in out

    def test_closing_syntax_correct(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer")]))
        assert "}));" in out

    def test_table_name_matches_var_name(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Approval")]))
        assert 'onchainTable("approval"' in out
        assert "export const approval" in out


# ── camelCase naming ─────────────────────────────────────────────────────────

class TestNaming:
    def test_pascal_to_camel(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "TransferEvent")]))
        assert "export const transferEvent" in out

    def test_single_word(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer")]))
        assert "export const transfer" in out

    def test_all_caps_acronym(self):
        # TVL is all-uppercase → should become tvl (fully lowercased), not tVL.
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "TVL")]))
        assert "export const tvl" in out
        assert "tVL" not in out

    def test_mixed_acronym(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "AlchemistDeposit")]))
        assert "export const alchemistDeposit" in out

    def test_leading_acronym_followed_by_word(self):
        # TVLMetrics: run "TVL" followed by lowercase 'M' → tvlMetrics
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "TVLMetrics")]))
        assert "export const tvlMetrics" in out

    def test_leading_acronym_then_digit(self):
        # ERC20Transfer: run "ERC" stopped by '2' → erc20Transfer
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "ERC20Transfer")]))
        assert "export const erc20Transfer" in out

    def test_multiple_entities_unique_vars(self):
        nodes = [_entity("e1", "TransferA"), _entity("e2", "TransferB")]
        out = render_ponder_schema(_cfg(nodes=nodes))
        assert "export const transferA" in out
        assert "export const transferB" in out

    def test_duplicate_entity_name_disambiguated(self):
        """Two nodes with the same name get unique suffixed table names (transfer_e1, transfer_e2)
        rather than silently collapsing — both tables are preserved."""
        nodes = [_entity("e1", "Transfer"), _entity("e2", "Transfer")]
        out = render_ponder_schema(_cfg(nodes=nodes))
        # Both nodes should produce a table (with disambiguated suffixes)
        assert out.count("export const transfer") == 2
        assert "transfer_e1" in out
        assert "transfer_e2" in out


# ── ID field ──────────────────────────────────────────────────────────────────

class TestIdField:
    def test_id_field_is_primary_key(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer")]))
        assert "id: t.text().primaryKey()" in out

    def test_id_field_never_gets_notnull_suffix(self):
        """primaryKey() already implies not null; suffix should not be doubled."""
        fields = [_field("id", "ID", required=True)]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer", fields=fields)]))
        assert "id: t.text().primaryKey()" in out
        assert "primaryKey().notNull()" not in out


# ── Type mapping ──────────────────────────────────────────────────────────────

class TestTypeMapping:
    def _entity_with(self, fname, ftype, required=False):
        fields = [
            _field("id", "ID", required=True),
            _field(fname, ftype, required=required),
        ]
        return _entity("e1", "Test", fields=fields)

    def test_string_to_text(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("name", "String")]))
        assert "name: t.text()" in out

    def test_bigint_to_bigint(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("amount", "BigInt")]))
        assert "amount: t.bigint()" in out

    def test_int_to_integer(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("count", "Int")]))
        assert "count: t.integer()" in out

    def test_boolean_to_boolean(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("active", "Boolean")]))
        assert "active: t.boolean()" in out

    def test_bytes_to_hex(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("data", "Bytes")]))
        assert "data: t.hex()" in out

    def test_address_to_hex(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("owner", "Address")]))
        assert "owner: t.hex()" in out

    def test_bigdecimal_to_text_with_comment(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("price", "BigDecimal")]))
        assert "price: t.text()" in out
        assert "BigDecimal" in out or "text()" in out
        # Comment must be present
        assert "/*" in out

    def test_id_type_field_is_primary_key(self):
        out = render_ponder_schema(_cfg(nodes=[self._entity_with("id", "ID", required=True)]))
        assert "t.text().primaryKey()" in out


# ── required / notNull ────────────────────────────────────────────────────────

class TestNotNull:
    def test_required_field_gets_notnull(self):
        fields = [
            _field("id", "ID", required=True),
            _field("owner", "String", required=True),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert "owner: t.text().notNull()" in out

    def test_optional_field_no_notnull(self):
        fields = [
            _field("id", "ID", required=True),
            _field("owner", "String", required=False),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert "owner: t.text()\n" in out or "owner: t.text()," in out
        assert "owner: t.text().notNull()" not in out

    def test_bigdecimal_required_notnull_before_comment(self):
        """notNull() must come before the /* */ comment, not after."""
        fields = [
            _field("id", "ID", required=True),
            _field("price", "BigDecimal", required=True),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert "price: t.text().notNull()" in out
        # notNull should appear before the comment
        price_line = next(l for l in out.splitlines() if "price:" in l)
        notnull_pos = price_line.find(".notNull()")
        comment_pos = price_line.find("/*")
        assert notnull_pos < comment_pos, "notNull() should appear before the comment"

    def test_bigdecimal_optional_no_notnull(self):
        fields = [
            _field("id", "ID", required=True),
            _field("price", "BigDecimal", required=False),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert ".notNull()" not in out.split("price:")[1].split("\n")[0]


# ── derivedFrom fields ────────────────────────────────────────────────────────

class TestDerivedFrom:
    def test_derived_from_field_skipped(self):
        fields = [
            _field("id", "ID", required=True),
            _field("owner", "String"),
            _field("transfers", "Transfer", derived_from="owner"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Account", fields=fields)]))
        assert "transfers" not in out

    def test_non_derived_fields_still_emitted(self):
        fields = [
            _field("id", "ID", required=True),
            _field("owner", "String"),
            _field("transfers", "Transfer", derived_from="owner"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Account", fields=fields)]))
        assert "owner" in out


# ── List types ────────────────────────────────────────────────────────────────

class TestListTypes:
    def test_mappable_list_type_uses_native_array(self):
        """Primitive element types (BigInt, String, etc.) use t.<T>().array() syntax."""
        fields = [
            _field("id", "ID", required=True),
            _field("ids", "[BigInt!]"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert "ids: t.bigint().array()" in out

    def test_string_list_uses_native_array(self):
        fields = [
            _field("id", "ID", required=True),
            _field("tags", "[String!]"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert "tags: t.text().array()" in out

    def test_list_type_required_uses_notnull(self):
        """Required list field gets .notNull() after .array()."""
        fields = [
            _field("id", "ID", required=True),
            _field("ids", "[BigInt!]", required=True),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert "ids: t.bigint().array().notNull()" in out

    def test_bigdecimal_list_falls_back_to_json_text(self):
        """BigDecimal arrays can't use native array; fall back to JSON text."""
        fields = [
            _field("id", "ID", required=True),
            _field("prices", "[BigDecimal!]"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert "prices: t.text()" in out
        assert "JSON text" in out


# ── Entity reference fields ───────────────────────────────────────────────────

class TestEntityRefs:
    def test_entity_ref_stored_as_text(self):
        fields = [
            _field("id", "ID", required=True),
            _field("account", "Account"),  # "Account" is another entity type
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer", fields=fields)]))
        assert "account: t.text()" in out
        assert "ref → Account" in out

    def test_entity_ref_required(self):
        fields = [
            _field("id", "ID", required=True),
            _field("account", "Account", required=True),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer", fields=fields)]))
        assert "account: t.text().notNull()" in out


# ── relations() exports ───────────────────────────────────────────────────────

class TestRelations:
    """relations() exports are generated for entity-reference fields."""

    def _two_entity_cfg(self, derived=False):
        """Transfer references Token; optionally Token has a @derivedFrom back-ref."""
        token_fields = [_field("id", "ID", required=True)]
        if derived:
            token_fields.append(_field("transfers", "Transfer", derived_from="token"))

        transfer_fields = [
            _field("id", "ID", required=True),
            _field("token", "Token", required=True),
        ]
        return _cfg(nodes=[
            _entity("e1", "Token", fields=token_fields),
            _entity("e2", "Transfer", fields=transfer_fields),
        ])

    def test_relations_import_added(self):
        out = render_ponder_schema(self._two_entity_cfg())
        assert 'import { onchainTable, relations }' in out

    def test_no_relations_import_without_refs(self):
        """Schema with no entity refs should only import onchainTable."""
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Foo")]))
        assert 'relations' not in out

    def test_one_relation_emitted(self):
        out = render_ponder_schema(self._two_entity_cfg())
        assert "transferRelations = relations(transfer" in out

    def test_one_relation_uses_correct_fields(self):
        out = render_ponder_schema(self._two_entity_cfg())
        assert "one(token, { fields: [transfer.token], references: [token.id] })" in out

    def test_many_relation_from_derived_from(self):
        out = render_ponder_schema(self._two_entity_cfg(derived=True))
        assert "tokenRelations = relations(token" in out
        assert "many(transfer)" in out

    def test_derived_from_field_not_in_table(self):
        """@derivedFrom fields should not produce a column in onchainTable."""
        out = render_ponder_schema(self._two_entity_cfg(derived=True))
        # 'transfers:' must not appear inside the token onchainTable
        token_table = out.split("onchainTable")[1].split("}));")[0]
        assert "transfers:" not in token_table

    def test_external_ref_skipped(self):
        """A field referencing an entity not in the schema produces no relation export."""
        fields = [
            _field("id", "ID", required=True),
            _field("user", "ExternalEntity"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer", fields=fields)]))
        assert "transferRelations" not in out

    def test_no_relations_for_primitives(self):
        """Primitive-typed fields don't produce relations."""
        fields = [
            _field("id", "ID", required=True),
            _field("amount", "BigInt"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer", fields=fields)]))
        assert "relations" not in out


# ── aggregateentity nodes ─────────────────────────────────────────────────────

class TestAggregateEntity:
    def test_aggregate_entity_emitted(self):
        out = render_ponder_schema(_cfg(nodes=[_agg("a1", "Counter")]))
        assert "export const counter = onchainTable" in out

    def test_aggregate_fields_emitted(self):
        fields = [
            _field("id", "ID", required=True),
            _field("count", "BigInt", required=True),
        ]
        out = render_ponder_schema(_cfg(nodes=[_agg("a1", "Counter", fields=fields)]))
        assert "count: t.bigint().notNull()" in out

    def test_entity_and_aggregate_both_emitted(self):
        out = render_ponder_schema(_cfg(nodes=[
            _entity("e1", "Transfer"),
            _agg("a1", "Counter"),
        ]))
        assert "export const transfer" in out
        assert "export const counter" in out


# ── Duplicate and edge-case field names ───────────────────────────────────────

class TestEdgeCases:
    def test_duplicate_field_names_only_once(self):
        """Duplicate field names in the same entity should not double-emit."""
        fields = [
            _field("id", "ID", required=True),
            _field("owner", "String"),
            _field("owner", "String"),  # duplicate
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        assert out.count("owner:") == 1

    def test_empty_field_name_skipped(self):
        fields = [
            _field("id", "ID", required=True),
            _field("", "String"),  # empty name
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "T", fields=fields)]))
        # Should not emit a blank field line
        assert ": t.text()," not in out.replace("id: t.text().primaryKey(),", "")

    def test_unnamed_entity_skipped(self):
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "")]))
        assert "export const" not in out

    def test_multiple_fields_all_emitted(self):
        fields = [
            _field("id", "ID", required=True),
            _field("from", "String"),
            _field("to", "String"),
            _field("value", "BigInt"),
            _field("timestamp", "BigInt"),
        ]
        out = render_ponder_schema(_cfg(nodes=[_entity("e1", "Transfer", fields=fields)]))
        for fname in ("from", "to", "value", "timestamp"):
            assert fname in out
