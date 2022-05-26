# AutoTransform
# Large scale, component based code modification library
#
# Licensed under the MIT License <http://opensource.org/licenses/MIT>
# SPDX-License-Identifier: MIT
# Copyright (c) 2022-present Nathan Rockenbach <http://github.com/nathro>

# @black_format

"""Utility methods for getting user input for AutoTransform."""

from getpass import getpass
from typing import List, Optional

from colorama import Fore

ERROR_COLOR = Fore.RED
INFO_COLOR = Fore.YELLOW
INPUT_COLOR = Fore.GREEN
RESET_COLOR = Fore.RESET


def info(text: str) -> None:
    """Prints a string of text as info to the console.

    Args:
        text (str): The text to print.
    """

    print(f"{INFO_COLOR}{text}{RESET_COLOR}")


def error(text: str) -> None:
    """Prints a string of text as error to the console.

    Args:
        text (str): The text to print.
    """

    print(f"{ERROR_COLOR}{text}{RESET_COLOR}")


def get_str(prompt: str, secret: bool = False) -> str:
    """Prompts the user to input a value.

    Args:
        prompt (str): The prompt to give to the user
        secret (bool, optional): Whether to use getpass for input. Defaults to False.

    Returns:
        str: The input value.
    """

    if secret:
        return getpass(f"{INFO_COLOR}{prompt}{RESET_COLOR}")
    return input(f"{INFO_COLOR}{prompt}{RESET_COLOR}")


def choose_string_option(prompt: str, options: List[str | List[str]]) -> str:
    """Prompts the user to choose one of a set of options. All options should
    be lowercase.

    Args:
        prompt (str): The prompt to give the user.
        options (List[str  |  List[str]]): The potential options to choose. If a list
            is an option, then the first value of the list will be returned if any of
            the list is chosen.

    Returns:
        str: The selected option
    """

    assert len(options) > 0, "Choosing from an empty list of options is not possible."
    option_list = [option if isinstance(option, str) else option[0] for option in options]
    while True:
        choice = get_str(f"{prompt}({'/'.join(option_list)}) ").lower()
        for option in options:
            if isinstance(option, str) and choice == option:
                return option

            if isinstance(option, List) and choice in option:
                return option[0]

        error(f"Invalid choice, choose one of: {', '.join(option_list)}")


def choose_yes_or_no(prompt: str) -> bool:
    """Gives the user a yes or no prompt.

    Args:
        prompt (str): The prompt to give to the user.

    Returns:
        bool: If the user chose yes.
    """

    return choose_string_option(prompt, [["y", "yes"], ["n", "no"]]) == "y"


def input_string(
    prompt: str,
    name: str,
    previous: Optional[str] = None,
    default: Optional[str] = None,
    secret: bool = False,
) -> str:
    """Prompts the user to input a value, or potentially use a previously input value/default value.

    Args:
        prompt (str): The prompt to give to the user.
        name (str): The name of the value being prompted for.
        previous (Optional[str], optional): The previously input value. Defaults to None.
        default (Optional[str], optional): The default value. Defaults to None.
        secret (bool, optional): Whether to use getpass for inputs. Defaults to False.

    Returns:
        str: The value entered by the user.
    """

    # Check if the previous value should be used
    # Ignore previous value if it is the same as default
    if (
        previous is not None
        and previous != default
        and choose_yes_or_no(f"Use previous {name} ({previous})?")
    ):
        return previous

    # Check if the user wants to use the default value
    if default is not None and choose_yes_or_no(f"Use default {name}?"):
        return default

    return get_str(f"{prompt} ", secret)


def input_int(prompt: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """Gets an integer input form the user within the specified range.

    Args:
        prompt (str): The prompt to give the user.
        min_val (Optional[int], optional): The minimum acceptable value. Defaults to None.
        max_val (Optional[int], optional): The maximum acceptable value. Defaults to None.

    Returns:
        int: The integer specified by the user.
    """

    if min_val is not None and max_val is not None:
        assert min_val <= max_val, "The minimum valid value must be less than the maximum"
        if min_val == max_val:
            # If there's only one choice, just return it
            return min_val
        range_str = f"({min_val}-{max_val})"
    elif min_val is not None:
        range_str = f"(>={min_val})"
    elif max_val is not None:
        range_str = f"(<={max_val})"
    else:
        range_str = ""

    while True:
        str_val = get_str(f"{prompt}{range_str} ")
        if str_val.startswith("-"):
            is_negative = True
            str_val = str_val[1:]
        if not str_val.isdigit():
            error("Only a decimal number may be entered")
            continue
        int_val = -int(str_val) if is_negative else int(str_val)
        if min_val is not None and int_val < min_val:
            error(f"{int_val} is too low, must be at least {min_val}")
            continue
        if max_val is not None and int_val > max_val:
            error(f"{int_val} is too high, must be less than {max_val}")
            continue
        return int_val
