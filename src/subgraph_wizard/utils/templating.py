"""Template rendering utilities."""

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Cache the template environment
_template_env: Environment | None = None


def get_template_env() -> Environment:
    """Get the Jinja2 template environment.
    
    The template directory is resolved relative to the package root,
    pointing to the 'templates/' directory at the project level.
    
    Returns:
        Jinja2 Environment configured with the templates directory.
    """
    global _template_env
    
    if _template_env is None:
        # Resolve templates directory relative to package root
        # __file__ is in src/subgraph_wizard/utils/templating.py
        # We need to go up to the project root: ../../../templates
        package_root = Path(__file__).parent.parent.parent.parent
        templates_dir = package_root / "templates"
        
        logger.debug(f"Initializing template environment from: {templates_dir}")
        
        if not templates_dir.exists():
            raise FileNotFoundError(f"Templates directory not found: {templates_dir}")
        
        _template_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(
                enabled_extensions=(),  # Disable for non-HTML templates
                default=False,
            ),
            keep_trailing_newline=True,  # Preserve trailing newlines in templates
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    return _template_env


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a template with the given context.
    
    Args:
        template_name: Name/path of the template file relative to templates/.
            Example: 'subgraph.yaml.j2' or 'mappings/mapping_auto.ts.j2'
        context: Dictionary of variables to pass to the template.
    
    Returns:
        Rendered template content as a string.
    
    Raises:
        jinja2.TemplateNotFound: If template doesn't exist.
        jinja2.TemplateError: If template rendering fails.
    """
    env = get_template_env()
    template = env.get_template(template_name)
    
    logger.debug(f"Rendering template: {template_name}")
    
    return template.render(**context)


def reset_template_env() -> None:
    """Reset the cached template environment.
    
    Useful for testing or when templates directory needs to change.
    """
    global _template_env
    _template_env = None
