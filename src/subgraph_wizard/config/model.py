"""Configuration data models."""

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal

logger = logging.getLogger(__name__)


# Type alias for relationship types
RelationType = Literal["one_to_one", "one_to_many", "many_to_many"]


@dataclass
class ContractConfig:
    """Configuration for a single contract to be indexed.
    
    Attributes:
        name: Human-readable name for the contract (used in entity naming).
        address: Contract address (0x + 40 hex chars).
        start_block: Block number to start indexing from.
        abi_path: Filename of the ABI JSON file (relative to abis/ directory).
        index_events: Whether to index events from this contract.
        call_handlers: List of function signatures to index (intermediate complexity).
            Example: ["transfer(address,uint256)", "approve(address,uint256)"]
        block_handler: Whether to enable block handler for this contract (intermediate complexity).
    """
    name: str
    address: str
    start_block: int
    abi_path: str
    index_events: bool = True
    call_handlers: Optional[list[str]] = None
    block_handler: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Only include intermediate fields if they have non-default values
        # to keep basic configs clean
        if result.get("call_handlers") is None:
            del result["call_handlers"]
        if not result.get("block_handler"):
            del result["block_handler"]
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "ContractConfig":
        """Create a ContractConfig from a dictionary.
        
        Args:
            data: Dictionary containing contract configuration.
        
        Returns:
            ContractConfig instance.
        
        Raises:
            KeyError: If required fields are missing.
        """
        return cls(
            name=data["name"],
            address=data["address"],
            start_block=data["start_block"],
            abi_path=data["abi_path"],
            index_events=data.get("index_events", True),
            call_handlers=data.get("call_handlers"),
            block_handler=data.get("block_handler", False),
        )


@dataclass
class TemplateConfig:
    """Configuration for a dynamic data source template (advanced complexity).
    
    Templates are used when contract addresses are not known at deployment time.
    They are instantiated at runtime when a factory contract emits an event
    that signals the creation of a new contract to index.
    
    Example use case: Uniswap V2 Pair factory creates new Pair contracts,
    and each new Pair should be indexed dynamically.
    
    Attributes:
        name: Template name (used in subgraph.yaml templates section).
        abi_path: Filename of the ABI JSON file (relative to abis/ directory).
        event_handlers: List of event names to handle in the template.
        source_contract: Name of the factory contract that instantiates this template.
        source_event: Event name that triggers template instantiation
            (e.g., "PairCreated" for Uniswap).
        index_events: Whether to index events from instantiated contracts.
        call_handlers: Optional list of function signatures to index (advanced).
        block_handler: Whether to enable block handler for instantiated contracts.
    """
    name: str
    abi_path: str
    event_handlers: list[str]
    source_contract: str
    source_event: str
    index_events: bool = True
    call_handlers: Optional[list[str]] = None
    block_handler: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "abi_path": self.abi_path,
            "event_handlers": self.event_handlers,
            "source_contract": self.source_contract,
            "source_event": self.source_event,
            "index_events": self.index_events,
        }
        # Only include optional fields if they have non-default values
        if self.call_handlers:
            result["call_handlers"] = self.call_handlers
        if self.block_handler:
            result["block_handler"] = self.block_handler
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "TemplateConfig":
        """Create a TemplateConfig from a dictionary.
        
        Args:
            data: Dictionary containing template configuration.
        
        Returns:
            TemplateConfig instance.
        
        Raises:
            KeyError: If required fields are missing.
        """
        return cls(
            name=data["name"],
            abi_path=data["abi_path"],
            event_handlers=data.get("event_handlers", []),
            source_contract=data["source_contract"],
            source_event=data["source_event"],
            index_events=data.get("index_events", True),
            call_handlers=data.get("call_handlers"),
            block_handler=data.get("block_handler", False),
        )


@dataclass
class EntityRelationship:
    """Configuration for a relationship between entities (advanced complexity).
    
    Entity relationships define how entities in the schema relate to each other.
    This enables generating proper GraphQL schema with references and derived fields.
    
    Attributes:
        from_entity: Name of the source entity (must match a contract name or event entity).
        to_entity: Name of the target entity.
        relation_type: Type of relationship:
            - "one_to_one": Single reference (e.g., Token -> Owner)
            - "one_to_many": Array of references (e.g., Factory -> [Pool])
            - "many_to_many": Many-to-many via join (e.g., User <-> Token)
        field_name: Field name on the source entity for this relationship.
        derived_from: For derived fields, the field on the target entity that
            references back to this entity. Used for reverse lookups.
            Example: Pool.factory derives from Factory.id
    """
    from_entity: str
    to_entity: str
    relation_type: str  # "one_to_one", "one_to_many", "many_to_many"
    field_name: str
    derived_from: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "relation_type": self.relation_type,
            "field_name": self.field_name,
        }
        if self.derived_from:
            result["derived_from"] = self.derived_from
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "EntityRelationship":
        """Create an EntityRelationship from a dictionary.
        
        Args:
            data: Dictionary containing relationship configuration.
        
        Returns:
            EntityRelationship instance.
        
        Raises:
            KeyError: If required fields are missing.
        """
        return cls(
            from_entity=data["from_entity"],
            to_entity=data["to_entity"],
            relation_type=data["relation_type"],
            field_name=data["field_name"],
            derived_from=data.get("derived_from"),
        )


@dataclass
class SubgraphConfig:
    """Configuration for a complete subgraph project.
    
    Attributes:
        name: Subgraph name (used in project directory and package.json).
        network: Network identifier (must be in SUPPORTED_NETWORKS).
        output_dir: Directory where the subgraph project will be generated.
        mappings_mode: Mapping generation mode ('stub' or 'auto').
        contracts: List of contracts to index.
        config_version: Configuration schema version for forward compatibility.
            - Version 1: Basic complexity only (events)
            - Version 2: Adds intermediate complexity (call/block handlers)
            - Version 3: Adds advanced complexity (templates, relationships)
        complexity: Complexity level ('basic', 'intermediate', 'advanced').
        templates: List of dynamic data source templates (advanced complexity).
            Used for indexing contracts created at runtime (e.g., factory patterns).
        entity_relationships: List of relationships between entities (advanced complexity).
            Used for defining how entities reference each other in the schema.
    """
    name: str
    network: str
    output_dir: str
    mappings_mode: str
    contracts: list[ContractConfig] = field(default_factory=list)
    config_version: int = 1
    complexity: str = "basic"
    templates: list[TemplateConfig] = field(default_factory=list)
    entity_relationships: list[EntityRelationship] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Determine config version based on complexity
        version = self.config_version
        if self.complexity == "intermediate" and version < 2:
            version = 2
        elif self.complexity == "advanced" and version < 3:
            version = 3
        
        result = {
            "config_version": version,
            "name": self.name,
            "network": self.network,
            "output_dir": self.output_dir,
            "complexity": self.complexity,
            "mappings_mode": self.mappings_mode,
            "contracts": [c.to_dict() for c in self.contracts],
        }
        
        # Only include advanced fields if they have non-empty values
        # to keep basic/intermediate configs clean
        if self.templates:
            result["templates"] = [t.to_dict() for t in self.templates]
        if self.entity_relationships:
            result["entity_relationships"] = [r.to_dict() for r in self.entity_relationships]
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "SubgraphConfig":
        """Create a SubgraphConfig from a dictionary.
        
        Supports version 1 (basic), version 2 (intermediate), and version 3 (advanced) configs.
        Lower version configs are automatically compatible - advanced fields
        will be initialized with defaults (empty lists).
        
        Args:
            data: Dictionary containing subgraph configuration.
        
        Returns:
            SubgraphConfig instance.
        
        Raises:
            KeyError: If required fields are missing.
        """
        contracts = [
            ContractConfig.from_dict(c) for c in data.get("contracts", [])
        ]
        
        # Parse templates if present (advanced complexity)
        templates = [
            TemplateConfig.from_dict(t) for t in data.get("templates", [])
        ]
        
        # Parse entity relationships if present (advanced complexity)
        entity_relationships = [
            EntityRelationship.from_dict(r) for r in data.get("entity_relationships", [])
        ]
        
        return cls(
            name=data["name"],
            network=data["network"],
            output_dir=data["output_dir"],
            mappings_mode=data["mappings_mode"],
            contracts=contracts,
            config_version=data.get("config_version", 1),
            complexity=data.get("complexity", "basic"),
            templates=templates,
            entity_relationships=entity_relationships,
        )
