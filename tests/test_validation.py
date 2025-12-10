"""Tests for configuration validation logic."""

import pytest

from subgraph_wizard.config.model import (
    ContractConfig,
    SubgraphConfig,
    TemplateConfig,
    EntityRelationship,
)
from subgraph_wizard.config.validation import (
    validate_config,
    validate_contract,
    validate_address,
    validate_template,
    validate_entity_relationship,
    VALID_MAPPING_MODES,
    VALID_COMPLEXITY_LEVELS,
    VALID_RELATION_TYPES,
)
from subgraph_wizard.errors import ValidationError
from subgraph_wizard.networks import SUPPORTED_NETWORKS


def make_valid_contract(
    name="TestToken",
    address="0x1234567890123456789012345678901234567890",
    start_block=12345678,
    abi_path="TestToken.json",
    index_events=True
):
    """Helper to create a valid ContractConfig for testing."""
    return ContractConfig(
        name=name,
        address=address,
        start_block=start_block,
        abi_path=abi_path,
        index_events=index_events
    )


def make_valid_config(
    name="my-subgraph",
    network="ethereum",
    output_dir="./output",
    mappings_mode="auto",
    contracts=None,
    config_version=1,
    complexity="basic"
):
    """Helper to create a valid SubgraphConfig for testing."""
    if contracts is None:
        contracts = [make_valid_contract()]
    
    return SubgraphConfig(
        name=name,
        network=network,
        output_dir=output_dir,
        mappings_mode=mappings_mode,
        contracts=contracts,
        config_version=config_version,
        complexity=complexity
    )


class TestValidateAddress:
    """Tests for address validation."""
    
    def test_valid_address_lowercase(self):
        """Test that lowercase hex address is valid."""
        validate_address(
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "TestContract"
        )  # Should not raise
    
    def test_valid_address_uppercase(self):
        """Test that uppercase hex address is valid."""
        validate_address(
            "0xABCDEF1234567890ABCDEF1234567890ABCDEF12",
            "TestContract"
        )  # Should not raise
    
    def test_valid_address_mixed_case(self):
        """Test that mixed case hex address is valid."""
        validate_address(
            "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12",
            "TestContract"
        )  # Should not raise
    
    def test_invalid_address_no_0x_prefix(self):
        """Test that address without 0x prefix is invalid."""
        with pytest.raises(ValidationError) as exc_info:
            validate_address(
                "1234567890123456789012345678901234567890",
                "TestContract"
            )
        
        assert "0x" in str(exc_info.value)
        assert "TestContract" in str(exc_info.value)
    
    def test_invalid_address_too_short(self):
        """Test that address with too few characters is invalid."""
        with pytest.raises(ValidationError) as exc_info:
            validate_address("0x123456789012345678901234567890123456789", "TestContract")
        
        assert "TestContract" in str(exc_info.value)
    
    def test_invalid_address_too_long(self):
        """Test that address with too many characters is invalid."""
        with pytest.raises(ValidationError) as exc_info:
            validate_address("0x12345678901234567890123456789012345678901", "TestContract")
        
        assert "TestContract" in str(exc_info.value)
    
    def test_invalid_address_non_hex_characters(self):
        """Test that address with non-hex characters is invalid."""
        with pytest.raises(ValidationError) as exc_info:
            validate_address("0xGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG", "TestContract")
        
        assert "TestContract" in str(exc_info.value)
    
    def test_invalid_address_empty(self):
        """Test that empty address is invalid."""
        with pytest.raises(ValidationError):
            validate_address("", "TestContract")
    
    def test_invalid_address_only_0x(self):
        """Test that '0x' alone is invalid."""
        with pytest.raises(ValidationError):
            validate_address("0x", "TestContract")


class TestValidateContract:
    """Tests for contract validation."""
    
    def test_valid_contract(self):
        """Test that a valid contract passes validation."""
        contract = make_valid_contract()
        validate_contract(contract)  # Should not raise
    
    def test_invalid_contract_empty_name(self):
        """Test that empty contract name fails validation."""
        contract = make_valid_contract(name="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_contract(contract)
        
        assert "name" in str(exc_info.value).lower()
        assert "empty" in str(exc_info.value).lower()
    
    def test_invalid_contract_whitespace_name(self):
        """Test that whitespace-only contract name fails validation."""
        contract = make_valid_contract(name="   ")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_contract(contract)
        
        assert "name" in str(exc_info.value).lower()
    
    def test_invalid_contract_bad_address(self):
        """Test that invalid address fails contract validation."""
        contract = make_valid_contract(address="invalid-address")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_contract(contract)
        
        assert "address" in str(exc_info.value).lower()
    
    def test_invalid_contract_negative_start_block(self):
        """Test that negative start_block fails validation."""
        contract = make_valid_contract(start_block=-1)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_contract(contract)
        
        assert "start_block" in str(exc_info.value).lower()
    
    def test_valid_contract_start_block_zero(self):
        """Test that start_block of 0 is valid."""
        contract = make_valid_contract(start_block=0)
        validate_contract(contract)  # Should not raise
    
    def test_invalid_contract_empty_abi_path(self):
        """Test that empty abi_path fails validation."""
        contract = make_valid_contract(abi_path="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_contract(contract)
        
        assert "abi" in str(exc_info.value).lower()


class TestValidateConfig:
    """Tests for full config validation."""
    
    def test_valid_config(self):
        """Test that a valid config passes validation."""
        config = make_valid_config()
        validate_config(config)  # Should not raise
    
    def test_valid_config_stub_mode(self):
        """Test that stub mapping mode is valid."""
        config = make_valid_config(mappings_mode="stub")
        validate_config(config)  # Should not raise
    
    def test_valid_config_auto_mode(self):
        """Test that auto mapping mode is valid."""
        config = make_valid_config(mappings_mode="auto")
        validate_config(config)  # Should not raise
    
    # Config version tests
    def test_invalid_config_version(self):
        """Test that unsupported config_version fails validation."""
        config = make_valid_config(config_version=99)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "config_version" in str(exc_info.value).lower()
    
    # Name tests
    def test_invalid_config_empty_name(self):
        """Test that empty subgraph name fails validation."""
        config = make_valid_config(name="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "name" in str(exc_info.value).lower()
    
    # Network tests
    def test_invalid_config_unknown_network(self):
        """Test that unknown network fails validation."""
        config = make_valid_config(network="unknown-network")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "network" in str(exc_info.value).lower()
        assert "unknown-network" in str(exc_info.value)
    
    def test_valid_config_all_supported_networks(self):
        """Test that all supported networks pass validation."""
        for network in SUPPORTED_NETWORKS:
            config = make_valid_config(network=network)
            validate_config(config)  # Should not raise
    
    # Output directory tests
    def test_invalid_config_empty_output_dir(self):
        """Test that empty output_dir fails validation."""
        config = make_valid_config(output_dir="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "output" in str(exc_info.value).lower()
    
    # Mapping mode tests
    def test_invalid_config_unknown_mapping_mode(self):
        """Test that unknown mapping mode fails validation."""
        config = make_valid_config(mappings_mode="unknown")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "mappings_mode" in str(exc_info.value).lower()
    
    def test_valid_config_all_mapping_modes(self):
        """Test that all valid mapping modes pass validation."""
        for mode in VALID_MAPPING_MODES:
            config = make_valid_config(mappings_mode=mode)
            validate_config(config)  # Should not raise
    
    # Complexity tests
    def test_invalid_config_unsupported_complexity(self):
        """Test that unsupported complexity fails validation."""
        config = make_valid_config(complexity="super-advanced")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "complexity" in str(exc_info.value).lower()
    
    def test_valid_config_all_complexity_levels(self):
        """Test that all valid complexity levels pass validation."""
        for level in VALID_COMPLEXITY_LEVELS:
            config = make_valid_config(complexity=level)
            validate_config(config)  # Should not raise
    
    # Contracts list tests
    def test_invalid_config_no_contracts(self):
        """Test that config with no contracts fails validation."""
        config = make_valid_config(contracts=[])
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "contract" in str(exc_info.value).lower()
    
    def test_valid_config_multiple_contracts(self):
        """Test that config with multiple valid contracts passes."""
        contracts = [
            make_valid_contract(
                name="TokenA",
                address="0x1111111111111111111111111111111111111111"
            ),
            make_valid_contract(
                name="TokenB",
                address="0x2222222222222222222222222222222222222222"
            ),
        ]
        config = make_valid_config(contracts=contracts)
        validate_config(config)  # Should not raise
    
    def test_invalid_config_duplicate_contract_names(self):
        """Test that duplicate contract names fail validation."""
        contracts = [
            make_valid_contract(
                name="SameName",
                address="0x1111111111111111111111111111111111111111"
            ),
            make_valid_contract(
                name="SameName",
                address="0x2222222222222222222222222222222222222222"
            ),
        ]
        config = make_valid_config(contracts=contracts)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "duplicate" in str(exc_info.value).lower()
        assert "name" in str(exc_info.value).lower()
    
    def test_invalid_config_duplicate_contract_addresses(self):
        """Test that duplicate contract addresses fail validation."""
        same_address = "0x1234567890123456789012345678901234567890"
        contracts = [
            make_valid_contract(name="TokenA", address=same_address),
            make_valid_contract(name="TokenB", address=same_address),
        ]
        config = make_valid_config(contracts=contracts)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "duplicate" in str(exc_info.value).lower()
        assert "address" in str(exc_info.value).lower()
    
    def test_invalid_config_duplicate_addresses_different_case(self):
        """Test that duplicate addresses with different case fail validation."""
        contracts = [
            make_valid_contract(
                name="TokenA",
                address="0xABCDEF1234567890ABCDEF1234567890ABCDEF12"
            ),
            make_valid_contract(
                name="TokenB",
                address="0xabcdef1234567890abcdef1234567890abcdef12"
            ),
        ]
        config = make_valid_config(contracts=contracts)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "duplicate" in str(exc_info.value).lower()
    
    # Contract validation delegation
    def test_invalid_contract_in_config(self):
        """Test that invalid contract within config fails validation."""
        invalid_contract = make_valid_contract(address="invalid")
        config = make_valid_config(contracts=[invalid_contract])
        
        with pytest.raises(ValidationError):
            validate_config(config)


class TestNetworkSupport:
    """Tests for network metadata."""
    
    def test_supported_networks_not_empty(self):
        """Test that SUPPORTED_NETWORKS is not empty."""
        assert len(SUPPORTED_NETWORKS) > 0
    
    def test_ethereum_is_supported(self):
        """Test that Ethereum mainnet is supported."""
        assert "ethereum" in SUPPORTED_NETWORKS
    
    def test_network_has_explorer(self):
        """Test that networks have explorer info."""
        for network, info in SUPPORTED_NETWORKS.items():
            assert "explorer" in info, f"{network} missing explorer"
    
    def test_network_has_chain_id(self):
        """Test that networks have chain_id."""
        for network, info in SUPPORTED_NETWORKS.items():
            assert "chain_id" in info, f"{network} missing chain_id"


class TestIntermediateComplexity:
    """Tests for intermediate complexity validation."""
    
    def test_valid_intermediate_config(self):
        """Test that intermediate complexity config passes validation."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json",
            call_handlers=["transfer(address,uint256)"],
            block_handler=True,
        )
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[contract],
            config_version=2,
            complexity="intermediate",
        )
        validate_config(config)  # Should not raise
    
    def test_valid_intermediate_no_handlers(self):
        """Test that intermediate config without handlers is valid."""
        contract = ContractConfig(
            name="TestToken",
            address="0x1234567890123456789012345678901234567890",
            start_block=12345678,
            abi_path="TestToken.json",
            call_handlers=None,
            block_handler=False,
        )
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=[contract],
            config_version=2,
            complexity="intermediate",
        )
        validate_config(config)  # Should not raise
    
    def test_invalid_call_handler_signature_missing_parens(self):
        """Test that invalid call handler signature fails validation."""
        from subgraph_wizard.config.validation import validate_call_handler_signature
        
        with pytest.raises(ValidationError) as exc_info:
            validate_call_handler_signature("transfer", "TestContract")
        
        assert "Invalid call handler signature" in str(exc_info.value)
    
    def test_invalid_call_handler_signature_empty(self):
        """Test that empty call handler signature fails validation."""
        from subgraph_wizard.config.validation import validate_call_handler_signature
        
        with pytest.raises(ValidationError) as exc_info:
            validate_call_handler_signature("", "TestContract")
        
        assert "Empty call handler signature" in str(exc_info.value)
    
    def test_invalid_call_handler_signature_no_function_name(self):
        """Test that call handler without function name fails validation."""
        from subgraph_wizard.config.validation import validate_call_handler_signature
        
        with pytest.raises(ValidationError) as exc_info:
            validate_call_handler_signature("(address,uint256)", "TestContract")
        
        assert "missing function name" in str(exc_info.value)
    
    def test_valid_call_handler_signatures(self):
        """Test that valid call handler signatures pass validation."""
        from subgraph_wizard.config.validation import validate_call_handler_signature
        
        # These should not raise
        validate_call_handler_signature("transfer(address,uint256)", "TestContract")
        validate_call_handler_signature("approve(address,uint256)", "TestContract")
        validate_call_handler_signature("setOwner(address)", "TestContract")
        validate_call_handler_signature("noParams()", "TestContract")
    
    def test_config_version_2_supported(self):
        """Test that config version 2 is supported."""
        config = make_valid_config(config_version=2, complexity="intermediate")
        validate_config(config)  # Should not raise
    
    def test_intermediate_complexity_supported(self):
        """Test that intermediate complexity is now supported."""
        config = make_valid_config(complexity="intermediate", config_version=2)
        validate_config(config)  # Should not raise
    
    def test_advanced_complexity_supported(self):
        """Test that advanced complexity is now supported."""
        config = make_valid_config(complexity="advanced", config_version=3)
        validate_config(config)  # Should not raise


def make_valid_template(
    name="PairTemplate",
    abi_path="Pair.json",
    event_handlers=None,
    source_contract="Factory",
    source_event="PairCreated",
    index_events=True,
):
    """Helper to create a valid TemplateConfig for testing."""
    if event_handlers is None:
        event_handlers = ["Swap", "Sync"]
    return TemplateConfig(
        name=name,
        abi_path=abi_path,
        event_handlers=event_handlers,
        source_contract=source_contract,
        source_event=source_event,
        index_events=index_events,
    )


def make_valid_relationship(
    from_entity="Pool",
    to_entity="Factory",
    relation_type="one_to_one",
    field_name="factory",
    derived_from=None,
):
    """Helper to create a valid EntityRelationship for testing."""
    return EntityRelationship(
        from_entity=from_entity,
        to_entity=to_entity,
        relation_type=relation_type,
        field_name=field_name,
        derived_from=derived_from,
    )


class TestAdvancedComplexity:
    """Tests for advanced complexity features (templates and entity relationships)."""
    
    def test_config_version_3_supported(self):
        """Test that config version 3 is supported."""
        config = make_valid_config(config_version=3, complexity="advanced")
        validate_config(config)  # Should not raise
    
    def test_valid_advanced_config_with_templates(self):
        """Test that advanced config with templates passes validation."""
        contracts = [make_valid_contract(name="Factory")]
        template = make_valid_template(source_contract="Factory")
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=contracts,
            config_version=3,
            complexity="advanced",
            templates=[template],
        )
        validate_config(config)  # Should not raise
    
    def test_valid_advanced_config_with_relationships(self):
        """Test that advanced config with entity relationships passes validation."""
        contracts = [make_valid_contract(name="Factory")]
        relationship = make_valid_relationship(from_entity="Pool", to_entity="Factory")
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=contracts,
            config_version=3,
            complexity="advanced",
            entity_relationships=[relationship],
        )
        validate_config(config)  # Should not raise
    
    def test_invalid_template_empty_name(self):
        """Test that template with empty name fails validation."""
        template = make_valid_template(name="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_template(template, {"Factory"})
        
        assert "name" in str(exc_info.value).lower()
    
    def test_invalid_template_empty_abi_path(self):
        """Test that template with empty abi_path fails validation."""
        template = make_valid_template(abi_path="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_template(template, {"Factory"})
        
        assert "abi" in str(exc_info.value).lower()
    
    def test_invalid_template_unknown_source_contract(self):
        """Test that template referencing unknown source contract fails validation."""
        template = make_valid_template(source_contract="UnknownFactory")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_template(template, {"Factory"})
        
        assert "source_contract" in str(exc_info.value).lower()
    
    def test_invalid_template_empty_source_event(self):
        """Test that template with empty source_event fails validation."""
        template = make_valid_template(source_event="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_template(template, {"Factory"})
        
        assert "source event" in str(exc_info.value).lower()
    
    def test_invalid_template_no_event_handlers(self):
        """Test that template with no event handlers fails validation."""
        template = make_valid_template(event_handlers=[])
        
        with pytest.raises(ValidationError) as exc_info:
            validate_template(template, {"Factory"})
        
        assert "event handler" in str(exc_info.value).lower()
    
    def test_invalid_relationship_empty_from_entity(self):
        """Test that relationship with empty from_entity fails validation."""
        relationship = make_valid_relationship(from_entity="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_entity_relationship(relationship, {"Factory"}, set())
        
        assert "from_entity" in str(exc_info.value).lower()
    
    def test_invalid_relationship_empty_to_entity(self):
        """Test that relationship with empty to_entity fails validation."""
        relationship = make_valid_relationship(to_entity="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_entity_relationship(relationship, {"Factory"}, set())
        
        assert "to_entity" in str(exc_info.value).lower()
    
    def test_invalid_relationship_empty_field_name(self):
        """Test that relationship with empty field_name fails validation."""
        relationship = make_valid_relationship(field_name="")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_entity_relationship(relationship, {"Factory"}, set())
        
        assert "field_name" in str(exc_info.value).lower()
    
    def test_invalid_relationship_bad_relation_type(self):
        """Test that relationship with invalid relation_type fails validation."""
        relationship = make_valid_relationship(relation_type="invalid_type")
        
        with pytest.raises(ValidationError) as exc_info:
            validate_entity_relationship(relationship, {"Factory"}, set())
        
        assert "relation_type" in str(exc_info.value).lower()
    
    def test_valid_relationship_all_relation_types(self):
        """Test that all valid relation types pass validation."""
        for rel_type in VALID_RELATION_TYPES:
            relationship = make_valid_relationship(relation_type=rel_type)
            validate_entity_relationship(relationship, {"Factory"}, set())  # Should not raise
    
    def test_duplicate_template_names_fail_validation(self):
        """Test that duplicate template names fail validation."""
        contracts = [make_valid_contract(name="Factory")]
        template1 = make_valid_template(name="SameTemplate")
        template2 = make_valid_template(name="SameTemplate")
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=contracts,
            config_version=3,
            complexity="advanced",
            templates=[template1, template2],
        )
        
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        
        assert "duplicate" in str(exc_info.value).lower()
    
    def test_templates_ignored_for_basic_complexity(self, caplog):
        """Test that templates are warned about when complexity is basic."""
        import logging
        caplog.set_level(logging.WARNING)
        
        contracts = [make_valid_contract(name="Factory")]
        template = make_valid_template(source_contract="Factory")
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=contracts,
            config_version=1,
            complexity="basic",
            templates=[template],
        )
        validate_config(config)  # Should not raise, but warn
        
        assert any("template" in record.message.lower() for record in caplog.records)
    
    def test_relationships_ignored_for_intermediate_complexity(self, caplog):
        """Test that relationships are warned about when complexity is intermediate."""
        import logging
        caplog.set_level(logging.WARNING)
        
        contracts = [make_valid_contract()]
        relationship = make_valid_relationship()
        
        config = SubgraphConfig(
            name="my-subgraph",
            network="ethereum",
            output_dir="./output",
            mappings_mode="auto",
            contracts=contracts,
            config_version=2,
            complexity="intermediate",
            entity_relationships=[relationship],
        )
        validate_config(config)  # Should not raise, but warn
        
        assert any("relationship" in record.message.lower() for record in caplog.records)

