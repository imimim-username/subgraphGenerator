"""Load ABI from pasted JSON.

This module provides functionality to load and validate ABI JSON from
user-provided text input (e.g., pasted in terminal).
"""

import json
import logging
import sys
from typing import Any

from subgraph_wizard.errors import ValidationError
from subgraph_wizard.abi.utils import validate_abi

logger = logging.getLogger(__name__)


def load_abi_from_paste(text: str) -> list[dict[str, Any]]:
    """Load an ABI from pasted JSON text.
    
    Args:
        text: JSON text containing the ABI.
    
    Returns:
        Parsed ABI as a list of dictionaries.
    
    Raises:
        ValidationError: If the text is not valid ABI JSON.
    """
    if not text or not text.strip():
        raise ValidationError("No ABI content provided")
    
    text = text.strip()
    
    # Parse JSON
    try:
        abi = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}")
    
    # Validate structure
    if not isinstance(abi, list):
        raise ValidationError(f"ABI must be a JSON array, got {type(abi).__name__}")
    
    # Validate ABI structure
    validate_abi(abi)
    
    logger.debug(f"Successfully parsed pasted ABI with {len(abi)} entries")
    return abi


def read_multiline_input(prompt: str = "", end_marker: str = "END") -> str:
    """Read multi-line input from the user until end marker or EOF.
    
    This function allows users to paste multi-line JSON content in the
    terminal. Input is collected until the user enters the end marker
    on its own line, or sends EOF (Ctrl+D on Unix, Ctrl+Z on Windows).
    
    Args:
        prompt: Initial prompt to display to the user.
        end_marker: String that signals end of input when entered on its own line.
    
    Returns:
        Collected input text (without the end marker).
    """
    if prompt:
        print(prompt)
    
    print(f"(Enter '{end_marker}' on a new line when done, or press Ctrl+D/Ctrl+Z)")
    
    lines = []
    
    try:
        while True:
            try:
                line = input()
            except EOFError:
                # User pressed Ctrl+D (Unix) or Ctrl+Z (Windows)
                break
            
            if line.strip() == end_marker:
                break
            
            lines.append(line)
    except KeyboardInterrupt:
        print("\nInput cancelled.")
        return ""
    
    return "\n".join(lines)


def load_abi_interactive(end_marker: str = "END") -> list[dict[str, Any]]:
    """Interactively load an ABI from user input.
    
    Prompts the user to paste ABI JSON and collects input until the
    end marker is entered or EOF is received.
    
    Args:
        end_marker: String that signals end of input.
    
    Returns:
        Parsed ABI as a list of dictionaries.
    
    Raises:
        ValidationError: If the pasted content is not valid ABI JSON.
    """
    print("\nPaste your ABI JSON below:")
    
    text = read_multiline_input(end_marker=end_marker)
    
    if not text:
        raise ValidationError("No ABI content provided")
    
    return load_abi_from_paste(text)
