"""Configuration data models."""

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


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
        complexity: Complexity level ('basic', 'intermediate', 'advanced').
    """
    name: str
    network: str
    output_dir: str
    mappings_mode: str
    contracts: list[ContractConfig] = field(default_factory=list)
    config_version: int = 1
    complexity: str = "basic"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Determine config version based on complexity
        version = self.config_version
        if self.complexity == "intermediate" and version < 2:
            version = 2
        
        return {
            "config_version": version,
            "name": self.name,
            "network": self.network,
            "output_dir": self.output_dir,
            "complexity": self.complexity,
            "mappings_mode": self.mappings_mode,
            "contracts": [c.to_dict() for c in self.contracts],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SubgraphConfig":
        """Create a SubgraphConfig from a dictionary.
        
        Supports both version 1 (basic) and version 2 (intermediate) configs.
        Version 1 configs are automatically compatible - intermediate fields
        will be initialized with defaults.
        
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
        
        return cls(
            name=data["name"],
            network=data["network"],
            output_dir=data["output_dir"],
            mappings_mode=data["mappings_mode"],
            contracts=contracts,
            config_version=data.get("config_version", 1),
            complexity=data.get("complexity", "basic"),
        )
