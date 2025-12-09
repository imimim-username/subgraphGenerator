"""Custom exception classes for Subgraph Wizard."""

import logging

logger = logging.getLogger(__name__)


class SubgraphWizardError(Exception):
    """Base exception for all Subgraph Wizard errors."""
    pass


class ValidationError(SubgraphWizardError):
    """Raised when configuration validation fails."""
    pass


class AbiFetchError(SubgraphWizardError):
    """Raised when ABI fetching fails."""
    pass
