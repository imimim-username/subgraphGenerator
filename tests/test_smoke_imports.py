"""Smoke tests to verify key modules can be imported."""

import pytest


def test_import_main():
    """Test that main module can be imported."""
    import subgraph_wizard.main
    assert subgraph_wizard.main is not None


def test_import_cli():
    """Test that CLI module can be imported."""
    import subgraph_wizard.cli
    assert subgraph_wizard.cli is not None


def test_import_config():
    """Test that config modules can be imported."""
    import subgraph_wizard.config.model
    import subgraph_wizard.config.io
    import subgraph_wizard.config.validation
    assert subgraph_wizard.config.model is not None
    assert subgraph_wizard.config.io is not None
    assert subgraph_wizard.config.validation is not None


def test_import_errors():
    """Test that errors module can be imported."""
    import subgraph_wizard.errors
    assert subgraph_wizard.errors is not None


def test_import_networks():
    """Test that networks module can be imported."""
    import subgraph_wizard.networks
    assert subgraph_wizard.networks is not None
