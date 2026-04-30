"""Orchestrates the subgraph generation pipeline.

This module coordinates the full generation pipeline, loading ABIs
and calling individual generators to create the complete subgraph project.
"""

import logging
from pathlib import Path
from typing import Any

from subgraph_wizard.config.model import SubgraphConfig
from subgraph_wizard.generate.project_layout import prepare_project_structure
from subgraph_wizard.generate.subgraph_yaml import render_subgraph_yaml
from subgraph_wizard.generate.schema import render_schema
from subgraph_wizard.generate.mappings_auto import render_all_mappings_auto
from subgraph_wizard.generate.mappings_stub import render_all_mappings_stub
from subgraph_wizard.generate.package_json import render_package_json
from subgraph_wizard.generate.readme import render_readme
from subgraph_wizard.abi.local import load_abi_from_file
from subgraph_wizard.utils.fs_utils import safe_write

logger = logging.getLogger(__name__)

# Maximum characters to preview in dry-run mode
DRY_RUN_PREVIEW_LENGTH = 200


def _log_dry_run_file(path: Path, content: str) -> None:
    """Log what would be written in dry-run mode.
    
    Args:
        path: File path that would be written.
        content: Content that would be written.
    """
    size = len(content.encode('utf-8'))
    preview = content[:DRY_RUN_PREVIEW_LENGTH]
    if len(content) > DRY_RUN_PREVIEW_LENGTH:
        preview += "..."
    
    # Replace newlines with \n for cleaner preview
    preview_display = preview.replace('\n', '\\n')
    
    logger.info(f"[DRY RUN] Would write: {path} ({size} bytes)")
    logger.debug(f"[DRY RUN] Preview: {preview_display}")


def _load_abi_map(config: SubgraphConfig, abis_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load ABIs for all contracts and templates in the configuration.
    
    Attempts to load ABI files from the abis directory. If an ABI file
    doesn't exist, logs a warning and continues without it.
    
    For advanced complexity, also loads ABIs for templates.
    
    Args:
        config: Subgraph configuration.
        abis_dir: Path to the abis directory.
    
    Returns:
        Dictionary mapping contract/template names to their ABI data.
    """
    abi_map = {}
    
    # Load contract ABIs
    for contract in config.contracts:
        abi_path = abis_dir / contract.abi_path
        
        if abi_path.exists():
            try:
                abi = load_abi_from_file(abi_path)
                abi_map[contract.name] = abi
                logger.info(f"Loaded ABI for {contract.name} from {abi_path}")
            except Exception as e:
                logger.warning(f"Failed to load ABI for {contract.name}: {e}")
        else:
            logger.debug(f"ABI file not found for {contract.name}: {abi_path}")
    
    # Load template ABIs (advanced complexity)
    if config.complexity == "advanced" and config.templates:
        for template in config.templates:
            abi_path = abis_dir / template.abi_path
            
            if abi_path.exists():
                try:
                    abi = load_abi_from_file(abi_path)
                    abi_map[template.name] = abi
                    logger.info(f"Loaded ABI for template {template.name} from {abi_path}")
                except Exception as e:
                    logger.warning(f"Failed to load ABI for template {template.name}: {e}")
            else:
                logger.debug(f"ABI file not found for template {template.name}: {abi_path}")
    
    return abi_map


def generate_subgraph_project(config: SubgraphConfig, dry_run: bool = False) -> None:
    """Generate a complete subgraph project from configuration.
    
    This is the main entry point for subgraph generation. It orchestrates
    the full pipeline:
    
    1. Prepares the project directory structure
    2. Loads ABIs from the abis directory
    3. Renders subgraph.yaml manifest
    4. Renders schema.graphql
    5. Renders mapping files (based on mappings_mode)
    6. Renders package.json
    7. Renders README.md
    
    Args:
        config: Validated subgraph configuration.
        dry_run: If True, log what would be written without actually writing files.
    
    Raises:
        OSError: If files cannot be written.
    """
    mode_str = "[DRY RUN] " if dry_run else ""
    logger.info(f"{mode_str}Starting subgraph generation for: {config.name}")
    logger.info(f"{mode_str}Output directory: {config.output_dir}")
    logger.info(f"{mode_str}Network: {config.network}")
    logger.info(f"{mode_str}Mappings mode: {config.mappings_mode}")
    logger.info(f"{mode_str}Contracts: {len(config.contracts)}")
    
    # Step 1: Prepare project structure
    if not dry_run:
        paths = prepare_project_structure(config)
        root_dir = paths["root_dir"]
        abis_dir = paths["abis_dir"]
    else:
        root_dir = Path(config.output_dir)
        abis_dir = root_dir / "abis"
        logger.info(f"[DRY RUN] Would create directory structure in: {root_dir}")
        logger.info(f"[DRY RUN] Would create: {root_dir}/abis/")
        logger.info(f"[DRY RUN] Would create: {root_dir}/src/")
        logger.info(f"[DRY RUN] Would create: {root_dir}/src/mappings/")
    
    # Step 2: Load ABIs
    abi_map = _load_abi_map(config, abis_dir)
    if abi_map:
        logger.info(f"{mode_str}Loaded ABIs for {len(abi_map)} contracts")
    else:
        logger.info(f"{mode_str}No ABIs found, using placeholder entities and handlers")
    
    # Step 3: Render and write subgraph.yaml
    subgraph_yaml_content = render_subgraph_yaml(config, abi_map)
    subgraph_yaml_path = root_dir / "subgraph.yaml"
    
    if dry_run:
        _log_dry_run_file(subgraph_yaml_path, subgraph_yaml_content)
    else:
        safe_write(subgraph_yaml_path, subgraph_yaml_content)
        logger.info(f"Generated: {subgraph_yaml_path}")
    
    # Step 4: Render and write schema.graphql
    schema_content = render_schema(config, abi_map)
    schema_path = root_dir / "schema.graphql"
    
    if dry_run:
        _log_dry_run_file(schema_path, schema_content)
    else:
        safe_write(schema_path, schema_content)
        logger.info(f"Generated: {schema_path}")
    
    # Step 5: Render and write mapping files
    if config.mappings_mode == "auto":
        mappings = render_all_mappings_auto(config, abi_map)
    else:
        # Use stub mappings for "stub" mode (or any non-auto mode)
        mappings = render_all_mappings_stub(config, abi_map)
    
    for contract_name, mapping_content in mappings.items():
        mapping_path = root_dir / "src" / "mappings" / f"{contract_name}.ts"
        
        if dry_run:
            _log_dry_run_file(mapping_path, mapping_content)
        else:
            safe_write(mapping_path, mapping_content)
            logger.info(f"Generated: {mapping_path}")
    
    # Step 6: Render and write package.json
    package_json_content = render_package_json(config)
    package_json_path = root_dir / "package.json"
    
    if dry_run:
        _log_dry_run_file(package_json_path, package_json_content)
    else:
        safe_write(package_json_path, package_json_content)
        logger.info(f"Generated: {package_json_path}")
    
    # Step 7: Render and write README.md
    readme_content = render_readme(config, abi_map)
    readme_path = root_dir / "README.md"
    
    if dry_run:
        _log_dry_run_file(readme_path, readme_content)
    else:
        safe_write(readme_path, readme_content)
        logger.info(f"Generated: {readme_path}")
    
    # Summary
    if dry_run:
        logger.info("[DRY RUN] Generation preview complete. No files were written.")
    else:
        logger.info(f"Subgraph generation complete: {root_dir}")
        logger.info("Next steps:")
        logger.info(f"  1. cd {root_dir}")
        logger.info("  2. npm install  (or yarn)")
        logger.info("  3. npm run codegen")
        logger.info("  4. npm run build")
