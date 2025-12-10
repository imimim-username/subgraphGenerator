"""User prompt utility functions.

This module provides standardized prompt helpers for interactive user input,
including yes/no questions, text input, and choice selection.
"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)


def ask_string(
    prompt: str,
    default: str | None = None,
    validator: Callable[[str], bool] | None = None,
    error_message: str = "Invalid input. Please try again."
) -> str:
    """Ask the user for a string input.
    
    Args:
        prompt: The prompt to display to the user.
        default: Optional default value if user enters empty string.
        validator: Optional function to validate input (returns True if valid).
        error_message: Message to display when validation fails.
    
    Returns:
        The user's input string (or default if empty and default provided).
    
    Raises:
        KeyboardInterrupt: If user presses Ctrl+C.
        EOFError: If input stream is closed.
    """
    prompt_text = prompt
    if default is not None:
        prompt_text = f"{prompt} [{default}]: "
    else:
        prompt_text = f"{prompt}: "
    
    while True:
        try:
            response = input(prompt_text).strip()
        except EOFError:
            print()  # Add newline after EOF
            raise
        
        # Use default if empty response and default is provided
        if not response and default is not None:
            return default
        
        # Check if empty response without default
        if not response:
            print("Input cannot be empty. Please enter a value.")
            continue
        
        # Run validation if provided
        if validator is not None:
            if not validator(response):
                print(error_message)
                continue
        
        return response


def ask_choice(
    prompt: str,
    options: list[str],
    default_index: int = 0
) -> str:
    """Ask the user to choose from a list of options.
    
    Displays numbered options and asks user to select by number.
    
    Args:
        prompt: The prompt to display before options.
        options: List of option strings to choose from.
        default_index: Index of the default option (0-based).
    
    Returns:
        The selected option string.
    
    Raises:
        ValueError: If options list is empty or default_index is out of range.
        KeyboardInterrupt: If user presses Ctrl+C.
        EOFError: If input stream is closed.
    """
    if not options:
        raise ValueError("Options list cannot be empty")
    
    if default_index < 0 or default_index >= len(options):
        raise ValueError(f"default_index {default_index} is out of range for {len(options)} options")
    
    print(f"\n{prompt}")
    for i, option in enumerate(options):
        marker = "*" if i == default_index else " "
        print(f"  {marker}{i + 1}. {option}")
    
    default_num = default_index + 1
    
    while True:
        try:
            response = input(f"Enter choice (1-{len(options)}) [{default_num}]: ").strip()
        except EOFError:
            print()
            raise
        
        # Use default if empty
        if not response:
            return options[default_index]
        
        # Parse the number
        try:
            choice = int(response)
            if 1 <= choice <= len(options):
                return options[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(options)}.")
        except ValueError:
            print(f"Please enter a number between 1 and {len(options)}.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask the user a yes/no question.
    
    Args:
        prompt: The question to ask.
        default: Default response if user presses enter (True=Yes, False=No).
    
    Returns:
        True for yes, False for no.
    
    Raises:
        KeyboardInterrupt: If user presses Ctrl+C.
        EOFError: If input stream is closed.
    """
    if default:
        prompt_suffix = "[Y/n]"
    else:
        prompt_suffix = "[y/N]"
    
    while True:
        try:
            response = input(f"{prompt} {prompt_suffix}: ").strip().lower()
        except EOFError:
            print()
            raise
        
        # Empty response uses default
        if not response:
            return default
        
        if response in ("y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            print("Please enter 'y' or 'n'.")


def ask_int(
    prompt: str,
    default: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None
) -> int:
    """Ask the user for an integer input.
    
    Args:
        prompt: The prompt to display to the user.
        default: Optional default value if user enters empty string.
        min_value: Optional minimum allowed value (inclusive).
        max_value: Optional maximum allowed value (inclusive).
    
    Returns:
        The user's input as an integer.
    
    Raises:
        KeyboardInterrupt: If user presses Ctrl+C.
        EOFError: If input stream is closed.
    """
    prompt_text = prompt
    if default is not None:
        prompt_text = f"{prompt} [{default}]: "
    else:
        prompt_text = f"{prompt}: "
    
    while True:
        try:
            response = input(prompt_text).strip()
        except EOFError:
            print()
            raise
        
        # Use default if empty response and default is provided
        if not response and default is not None:
            return default
        
        if not response:
            print("Input cannot be empty. Please enter a number.")
            continue
        
        try:
            value = int(response)
        except ValueError:
            print("Invalid number. Please enter a valid integer.")
            continue
        
        # Check range
        if min_value is not None and value < min_value:
            print(f"Value must be at least {min_value}.")
            continue
        
        if max_value is not None and value > max_value:
            print(f"Value must be at most {max_value}.")
            continue
        
        return value
