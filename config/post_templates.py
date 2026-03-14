"""
Post templates configuration loader.

Loads post templates from YAML configuration file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from loguru import logger


DEFAULT_TEMPLATE = "breaking"

_templates_cache: Optional[dict] = None


def _load_templates() -> dict[str, Any]:
    """Load templates from YAML file."""
    global _templates_cache

    if _templates_cache is not None:
        return _templates_cache

    config_path = Path(__file__).parent / "post_templates.yaml"

    if not config_path.exists():
        logger.warning(f"Templates config not found: {config_path}")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        _templates_cache = yaml.safe_load(f)

    return _templates_cache or {}


def get_template(template_name: str) -> dict[str, Any]:
    """
    Get a template by name.

    Args:
        template_name: Name of the template (e.g., 'breaking', 'analysis')

    Returns:
        Template configuration dict

    Raises:
        ValueError: If template not found
    """
    templates = _load_templates()

    if not templates:
        logger.warning("No templates loaded, using default")
        return {}

    template = templates.get("templates", {}).get(template_name)

    if not template:
        raise ValueError(f"Template '{template_name}' not found")

    return template


def list_templates() -> list[str]:
    """List available template names."""
    templates = _load_templates()
    return list(templates.get("templates", {}).keys())
