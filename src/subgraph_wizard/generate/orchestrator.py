"""Orchestrates the subgraph generation pipeline."""

import logging
from pathlib import Path

from subgraph_wizard.config.model import SubgraphConfig
from subgraph_wizard.generate.project_layout import prepare_project_structure
from subgraph_wizard.generate.subgraph_yaml import render_subgraph_yaml
from subgraph_wizard.generate.schema import render_schema
from subgraph_wizard.generate.mappings_auto import render_all_mappings_auto
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


def generate_subgraph_project(config: SubgraphConfig, dry_run: bool = False) -> None:
    """Generate a complete subgraph project from configuration.
    
    This is the main entry point for subgraph generation. It orchestrates
    the full pipeline:
    
    1. Prepares the project directory structure
    2. Renders subgraph.yaml manifest
    3. Renders schema.graphql
    4. Renders mapping files (based on mappings_mode)
    
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
    else:
        root_dir = Path(config.output_dir)
        logger.info(f"[DRY RUN] Would create directory structure in: {root_dir}")
        logger.info(f"[DRY RUN] Would create: {root_dir}/abis/")
        logger.info(f"[DRY RUN] Would create: {root_dir}/src/")
        logger.info(f"[DRY RUN] Would create: {root_dir}/src/mappings/")
    
    # Step 2: Render and write subgraph.yaml
    subgraph_yaml_content = render_subgraph_yaml(config)
    subgraph_yaml_path = root_dir / "subgraph.yaml"
    
    if dry_run:
        _log_dry_run_file(subgraph_yaml_path, subgraph_yaml_content)
    else:
        safe_write(subgraph_yaml_path, subgraph_yaml_content)
        logger.info(f"Generated: {subgraph_yaml_path}")
    
    # Step 3: Render and write schema.graphql
    schema_content = render_schema(config)
    schema_path = root_dir / "schema.graphql"
    
    if dry_run:
        _log_dry_run_file(schema_path, schema_content)
    else:
        safe_write(schema_path, schema_content)
        logger.info(f"Generated: {schema_path}")
    
    # Step 4: Render and write mapping files
    if config.mappings_mode == "auto":
        mappings = render_all_mappings_auto(config)
        
        for contract_name, mapping_content in mappings.items():
            mapping_path = root_dir / "src" / "mappings" / f"{contract_name}.ts"
            
            if dry_run:
                _log_dry_run_file(mapping_path, mapping_content)
            else:
                safe_write(mapping_path, mapping_content)
                logger.info(f"Generated: {mapping_path}")
    else:
        # Stub mappings will be implemented in Milestone 7
        logger.warning(f"Mappings mode '{config.mappings_mode}' is not yet implemented. "
                      "Skipping mapping generation.")
    
    # Summary
    if dry_run:
        logger.info("[DRY RUN] Generation preview complete. No files were written.")
    else:
        logger.info(f"Subgraph generation complete: {root_dir}")
        logger.info("Next steps:")
        logger.info(f"  1. cd {root_dir}")
        logger.info("  2. npm install  (or yarn)")
        logger.info("  3. graph codegen")
        logger.info("  4. graph build")
