"""Work-in-progress tools to help set settings based on environment variables."""

import abc
import argparse
import os
import sys
from collections.abc import Iterable, Sized
from typing import Protocol, TypeGuard


class _MISSING:
    def __bool__(self):
        return False


MISSING = _MISSING()

MaybeString = str | None | _MISSING


# Mockable methods for interacting with the standard library.


def get_environ(key: str, default: MaybeString = MISSING) -> MaybeString:
    """Get a variable from the environment."""
    if key not in os.environ:
        return default
    return os.environ.get(key)


def stdout_is_a_tty() -> bool:
    """Check if std is a tty."""
    return sys.stdout.isatty()


def stdout_is_utf() -> bool:
    """Check stdout's reported encoding for the string UTF."""
    return "UTF" in sys.stdout.encoding.upper()


def stdout_supports_unicode() -> bool:
    """Guess if stdout likely supports Unicode or not."""
    if get_terminal() == "dumb":
        return False
    return stdout_is_utf()


def get_terminal() -> MaybeString:
    """Get the value of the TERM environment variable."""
    return get_environ("TERM")


def empty(value: Iterable | None) -> TypeGuard[str]:
    """Check if a value is a string and if it is empty."""
    if isinstance(value, str):
        return value is None or len(value.strip()) == 0
    return value is None or not value


def not_empty(value: Sized | None) -> TypeGuard[Sized]:
    """Verify that a value is not None and is truthy."""
    return value is not None and isinstance(value, Sized) and len(value) > 0


def not_empty_string(value: MaybeString) -> TypeGuard[str]:
    """Verify that a variable represents a non-empty string."""
    return value is not None and isinstance(value, str) and len(value.strip()) > 0


def env_fallbacks(var_names: list[str]) -> dict[str, MaybeString]:
    """Check for the environment variable we could fall back to."""
    fallbacks = {}
    for var_name in var_names:
        fallbacks[var_name] = get_environ(var_name)
    return fallbacks


def env_hint(k: str, v: MaybeString, prefix: str = "") -> str:
    """Make a hint for a value that can be derived from an environment variable."""
    if v is None or isinstance(v, _MISSING):
        v = "(not set)"
    elif "password" in k.lower() or ("token" in k.lower() and len(v)):
        v = "*** REDACTED ***"

    return f"{prefix}{k}={v}"


def add_argument(
    parser: argparse.ArgumentParser, argument_help: str, name: str, var_names: list[str], fallback: str | None = None
) -> None:
    """Add an argument with fallback environment variables."""
    dest = name.replace("-", "_")
    fallbacks = env_fallbacks(var_names)
    default = None
    for v in fallbacks.values():
        if v is not None:
            default = v
            break
    if default is None:
        default = fallback

    if stdout_is_utf():
        true_mark = "✓"
        dot_mark = "·"
    else:
        true_mark = "+"
        dot_mark = "-"

    environment_variable_helps = []
    has_found_default = False
    for k, v in fallbacks.items():
        if v is not None and has_found_default is False:
            prefix = f"  {true_mark} $"
        else:
            prefix = f"  {dot_mark} $"
        hint = env_hint(k, v, prefix)
        has_found_default = v is not None
        environment_variable_helps.append(hint)

    help_texts = [argument_help]
    metavar = None
    if len(var_names) == 1:
        metavar = var_names[0]
        environment_variable_help = environment_variable_helps[0].strip()
        help_texts.append(environment_variable_help)
    elif environment_variable_helps:
        environment_variable_help = environment_variable_helps.pop(0).strip()
        help_texts.append(f"Env: {environment_variable_help}")
        help_texts.extend([f"     {e.strip()}" for e in environment_variable_helps])
    if fallback is not None:
        help_texts.append(f"default: {fallback}")
    help_text = "\n".join(help_texts)
    parser.add_argument(f"--{name}", dest=dest, metavar=metavar, required=False, default=default, help=help_text)


class UseCliColor:
    """Precalculate some checks for if we should use colors or not."""

    def __init__(self) -> None:
        self.no_color = get_environ("NO_COLOR")
        self.cli_color = get_environ("CLICOLOR")
        self.cli_color_force = get_environ("CLICOLOR_FORCE")
        self.terminal = get_terminal()
        self.is_tty = stdout_is_a_tty()

    def guess_if_color_is_default(self) -> bool:
        """Determine if we should use colors or not."""
        if self.no_color:
            default_color = False
        elif self.cli_color_force:
            default_color = True
        elif self.terminal in {"xterm-mono", "dumb"}:
            default_color = False
        elif self.cli_color:
            default_color = self.is_tty
        else:
            default_color = self.is_tty
        return default_color


def add_color_arguments(parser: argparse.ArgumentParser) -> None:
    """Add colors arguments with default and explanations.

    See: https://no-color.org/ and https://bixense.com/clicolors/
    """
    color_use_decider = UseCliColor()
    no_color_hint = env_hint("NO_COLOR", color_use_decider.no_color, "$")
    cli_color_force_hint = env_hint("CLICOLOR_FORCE", color_use_decider.cli_color_force, "$")
    cli_color_hint = env_hint("CLICOLOR", color_use_decider.cli_color, "$")
    default_use_color = color_use_decider.guess_if_color_is_default()
    if color_use_decider.is_tty:
        is_tty_hint = "yes"
    else:
        is_tty_hint = "no"

    term_hint = env_hint("TERM", color_use_decider.terminal, "$")
    if color_use_decider.terminal == {"xterm-mono", "dumb"}:
        term_hint = f"{term_hint}: this TERM disables colors by default"
    elif not_empty_string(color_use_decider.terminal):
        term_hint = f"{term_hint}: this TERM probably allows colors"
    else:
        term_hint = f"{term_hint}: cannot guess this terminal's color capabilities"
    if default_use_color:
        default_color_hint = "Colors currently defaulting to on"
    else:
        default_color_hint = "Colors currently defaulting to off"

    colors_title = f"Enable colored highlighting? ({default_color_hint})"
    colors_help = f"""Env: {no_color_hint}: Set to 1 to disable colors by default
     {cli_color_force_hint}: Set to 1 to enable colors by default
     {cli_color_hint}: Set to 1 to enable colors if stdout is a tty ({is_tty_hint})
     {term_hint}

Force the color setting:""".rstrip()

    colors_group = parser.add_argument_group(colors_title, colors_help)
    colors = colors_group.add_mutually_exclusive_group(required=False)
    colors.add_argument(
        "--colors",
        dest="colors",
        action="store_true",
        default=default_use_color or None,
        help="Force colors on",
    )
    colors.add_argument(
        "--no-colors",
        dest="colors",
        action="store_false",
        default=None,
        help="Force colors off",
    )


def guess_boolean(value: MaybeString) -> bool:
    """Guess if a string represents truthiness or falsiness."""
    if value is None or isinstance(value, _MISSING):
        return False
    return f"{value}".lower() in {"true", "t", "y", "yes", "1"}


def add_boolean_argument(
    parser: argparse.ArgumentParser, argument_help: str | None, name: str, var_names: list[str], fallback: bool | None
) -> None:
    """Add two arguments, --thing and --no-thing, and optionally select a default."""
    help_texts = []
    dest = name.replace("-", "_")
    fallbacks = env_fallbacks(var_names)
    default_source = None
    default = None
    for k, v in fallbacks.items():
        if v is not None:
            default_source = k
            default = guess_boolean(v)
            break
    if default is None:
        default_source = "default"
        default = fallback

    environment_variable_helps = []
    has_found_default = False

    if stdout_is_utf():
        true_mark = "✓"
        false_mark = "✗"
        dot_mark = "·"
    else:
        true_mark = "+"
        false_mark = "✗"
        dot_mark = "-"

    for k, v in fallbacks.items():
        hint = env_hint(k, v, "$")
        if v is not None and has_found_default is False:
            if default:
                hint = f"{true_mark} {hint}"
            else:
                hint = f"{false_mark} {hint}"
        else:
            hint = f"{dot_mark} {hint}"
        has_found_default = v is not None
        environment_variable_helps.append(hint)
        if k == default_source:
            default_source = env_hint(k, v, "set by $")

    if environment_variable_helps:
        help_texts.extend([f"  {e.strip()}" for e in environment_variable_helps])
    help_text = "\n".join(help_texts)

    names = build_boolean_options_hint(name, default, default_source)

    title = build_boolean_title(name, argument_help)

    title = f"  {names} {title}"
    group = parser.add_argument_group(title, help_text)
    exclusive = group.add_mutually_exclusive_group(required=False)

    exclusive.add_argument(
        f"--{name}", dest=dest, required=False, action="store_true", default=default or None, help=argparse.SUPPRESS
    )
    exclusive.add_argument(
        f"--no-{name}", dest=dest, required=False, action="store_false", default=default, help=argparse.SUPPRESS
    )


def build_boolean_options_hint(name: str, default: bool | None, default_source: str | None) -> str:
    """Build the hints for turning the option on and off."""
    if default:
        return f"[--{name} ({default_source}) | --no-{name}]"
    if default is not None:
        return f"[--{name} | --no-{name} ({default_source})]"
    return f"[--{name} | --no-{name}]"


def build_boolean_title(name: str, argument_help: str | None) -> str:
    """Build the title of the boolean's exclusive group."""
    if not_empty_string(argument_help):
        if argument_help.endswith("?"):
            title = f"{argument_help} true/false"
        else:
            title = argument_help
    else:
        title = name.replace("-", " ").replace("_", " ").title()
    return title


class AHelpFormatter(argparse.RawTextHelpFormatter):
    """Tweaks outputted help."""

    def __init__(self, prog: str):
        super().__init__(prog, max_help_position=36)

    def format_help(self) -> str:
        """Turn an argument parser into help text."""
        lines = super().format_help().splitlines()
        # remove whitespace from the end of lines
        lines = [line.rstrip() for line in lines]
        # remove any extra newlines at the end
        help_text = "\n".join(lines).rstrip("\n")
        help_text = help_text.replace("\n\n  --", "\n  --")
        # ensure there is exactly one newline at the end
        return f"{help_text}\n"


class CanAddArgument(Protocol):
    """Matches ArgumentParser and the private argparse._ArgumentGroup."""

    def add_argument(self, *args, **kwargs) -> None:
        """Add an argument to this parser."""


class ArgumentBuilder(abc.ABC):
    """Build your arguments via these helpful classes."""

    def doc(self) -> str | None:
        """Return no documentation by default."""
        return None

    @property
    @abc.abstractmethod
    def default(self) -> MaybeString:
        """Return the default value for this argument."""

    @abc.abstractmethod
    def arg_name(self) -> str:
        """Return the name for the command line argument."""

    @abc.abstractmethod
    def field_name(self) -> str:
        """Return the name for field as attached to argparse."""

    def add_to_parser(self, parser: argparse.ArgumentParser | CanAddArgument) -> None:
        """Attach this field to a parser or argument group."""
        parser.add_argument(
            self.arg_name(),
            dest=self.field_name(),
            default=self.default,
            help=self.doc(),
        )


class FallbackToDefault(ArgumentBuilder):
    """Set up an argument with a default to use."""

    def __init__(self, field_name: str, fallback: MaybeString, doc: MaybeString = MISSING):
        self._field_name = field_name
        self.fallback = fallback
        self._doc = doc
        self.value = MISSING  # type: MaybeString

    @property
    def default(self) -> MaybeString:
        """Return the default value for the argument."""
        return self.fallback

    def doc(self) -> str | None:
        """Generate best-guess documentation for the argument."""
        doc = self._doc
        match doc:
            case _MISSING():
                doc = ""
            case None:
                doc = ""
        doc = doc.strip()
        if len(doc) and not doc.endswith("."):
            doc = f"{doc}. "
        match self.fallback:
            case _MISSING():
                return doc.strip()
            case _:
                return f"{doc}Defaults to {self.fallback!r}"

    def arg_name(self) -> str:
        """Turn the field name into an argument name."""
        return "--" + self._field_name.replace("_", "-").lower()

    def field_name(self) -> str:
        """Turn the field name into an argument name and then back into a field name."""
        return self.arg_name().removeprefix("--").replace("-", "_").lower()


class FallbackToEnv(ArgumentBuilder):
    """Look in the environment for a value for an argument."""

    def __init__(self, variable: str, fallback: MaybeString = MISSING, doc: MaybeString = MISSING):
        self.variable = variable
        self.fallback = fallback
        self._doc = doc
        self.value = MISSING  # type: MaybeString
        self._owner_name = None
        self._field_name = None

    @property
    def default(self) -> MaybeString:
        """Try to get the value for the argument."""
        return get_environ(self.variable, self.fallback)

    def doc(self) -> str | None:
        """Generate best-guess documentation for the argument."""
        doc = self._doc
        match doc:
            case _MISSING():
                doc = ""
            case None:
                doc = ""
        doc = doc.strip()
        if len(doc) and not doc.endswith("."):
            doc = f"{doc}. "
        env = get_environ(self.variable, _MISSING())
        match env:
            case _MISSING():
                variable = f"${self.variable} (unset)"
            case _:
                variable = f"${self.variable}={env!r}"
        match self.fallback:
            case _MISSING():
                pass
            case _:
                variable = f"{variable} or {self.fallback}"
        return f"{doc}Defaults to {variable!r}"

    def arg_name(self) -> str:
        """Get the argument name."""
        arg_name = self._field_name or self.variable
        return "--" + arg_name.replace("_", "-").lower()

    def field_name(self) -> str:
        """Get the field name."""
        return self.arg_name().removeprefix("--").replace("-", "_").lower()
