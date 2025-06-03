import abc
import argparse
import os
import sys
from collections.abc import Iterable, Sized
from typing import Any, Protocol, TypeGuard


class _MISSING: ...


MaybeString = str | None | _MISSING


def get_environ(key: str, default: Any | None = None) -> str | None:
    return os.environ.get(key, default)


def stdout_is_a_tty() -> bool:
    return sys.stdout.isatty()


def stdout_is_utf() -> bool:
    return "UTF" in sys.stdout.encoding.upper()


def stdout_supports_unicode() -> bool:
    if get_terminal() == "dumb":
        return False
    return stdout_is_utf()


def get_terminal() -> str | None:
    return get_environ("TERM")


def empty(value: Iterable | None) -> TypeGuard[str]:
    if isinstance(value, str):
        return value is None or len(value.strip()) == 0
    else:
        return value is None or not value


def not_empty(value: Sized | None) -> TypeGuard[Sized]:
    return value is not None and isinstance(value, Sized) and len(value) > 0


def not_empty_string(value: str | None) -> TypeGuard[str]:
    return value is not None and isinstance(value, str) and len(value.strip()) > 0


def env_fallbacks(var_names: list[str]) -> dict[str, str | None]:
    fallbacks = {}
    for var_name in var_names:
        fallbacks[var_name] = get_environ(var_name)
    return fallbacks


def env_hint(k: str, v: str | None, prefix: str = "") -> str:
    if "password" in k.lower() or "token" in k.lower() and v is not None and len(v):
        v = "*** REDACTED ***"
    elif v is None:
        v = "(not set)"

    return f"{prefix}{k}={v}"


def add_argument(
    parser: argparse.ArgumentParser, argument_help: str, name: str, var_names: list[str], fallback: str | None = None
):
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


def add_colors_argument(parser: argparse.ArgumentParser):
    """Add colors arguments with default and explanations.
    See: https://no-color.org/ and https://bixense.com/clicolors/
    """
    no_color = get_environ("NO_COLOR")
    cli_color = get_environ("CLICOLOR")
    cli_color_force = get_environ("CLICOLOR_FORCE")
    terminal = get_terminal()
    is_tty = stdout_is_a_tty()
    term_hint = env_hint("TERM", terminal, "$")
    if terminal == "xterm-mono" or terminal == "dumb":
        term_hint = f"{term_hint}: this TERM disables colors by default"
    elif not_empty_string(terminal):
        term_hint = f"{term_hint}: this TERM probably allows colors"
    else:
        term_hint = f"{term_hint}: cannot guess this terminal's color capabilities"

    if no_color:
        default_color = False
    elif cli_color_force:
        default_color = True
    elif terminal == "xterm-mono" or terminal == "dumb":
        default_color = False
    elif cli_color:
        default_color = is_tty
    else:
        default_color = is_tty

    no_color_hint = env_hint("NO_COLOR", no_color, "$")
    cli_color_force_hint = env_hint("CLICOLOR_FORCE", cli_color_force, "$")
    cli_color_hint = env_hint("CLICOLOR", cli_color, "$")

    if is_tty:
        is_tty_hint = "yes"
    else:
        is_tty_hint = "no"

    if default_color:
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
        default=default_color or None,
        help="Force colors on",
    )
    colors.add_argument(
        "--no-colors",
        dest="colors",
        action="store_false",
        default=None,
        help="Force colors off",
    )


def guess_boolean(value: str) -> bool:
    return value.lower() in {"true", "t", "y", "yes", "1"}


def add_boolean_argument(
    parser: argparse.ArgumentParser, argument_help: str | None, name: str, var_names: list[str], fallback: bool
):
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

    if len(environment_variable_helps):
        help_texts.extend([f"  {e.strip()}" for e in environment_variable_helps])
    help_text = "\n".join(help_texts)

    if default:
        names = f"[--{name} ({default_source}) | --no-{name}]"
    elif default is not None:
        names = f"[--{name} | --no-{name} ({default_source})]"
    else:
        names = f"[--{name} | --no-{name}]"

    if not_empty_string(argument_help):
        if argument_help.endswith("?"):
            title = f"{argument_help} true/false"
        else:
            title = argument_help
    else:
        title = name.replace("-", " ").replace("_", " ").title()
    title = f"  {names} {title}"

    group = parser.add_argument_group(title, help_text)
    exclusive = group.add_mutually_exclusive_group(required=False)

    exclusive.add_argument(
        f"--{name}", dest=dest, required=False, action="store_true", default=default or None, help=argparse.SUPPRESS
    )
    exclusive.add_argument(
        f"--no-{name}", dest=dest, required=False, action="store_false", default=default, help=argparse.SUPPRESS
    )


class AHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=36)

    def format_help(self):
        lines = super().format_help().splitlines()
        # remove whitespace from the end of lines
        lines = [line.rstrip() for line in lines]
        # remove any extra newlines at the end
        help_text = "\n".join(lines).rstrip("\n")
        help_text = help_text.replace("\n\n  --", "\n  --")
        # ensure there is exactly one newline at the end
        return f"{help_text}\n"


class CanAddArgument(Protocol):
    """This covers the private argparse._ArgumentGroup"""

    def add_argument(self, *args, **kwargs): ...


class ArgumentBuilder(abc.ABC):
    default = None

    def doc(self) -> str | None:
        return None

    def arg_name(self) -> str:
        raise NotImplementedError

    def field_name(self):
        raise NotImplementedError

    def add_to_parser(self, parser: argparse.ArgumentParser | CanAddArgument):
        parser.add_argument(
            self.arg_name(),
            dest=self.field_name(),
            default=self.default,
            help=self.doc(),
        )


class FallbackToDefault(ArgumentBuilder):
    def __init__(self, field_name: str, fallback: MaybeString, doc: MaybeString = _MISSING()):
        self._field_name = field_name
        self.fallback = fallback
        self._doc = doc
        self.value = _MISSING()  # type: MaybeString

    @property
    def default(self) -> str | _MISSING | None:  # type: ignore[override]
        return self.fallback

    def doc(self) -> str | None:
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
        return "--" + self._field_name.replace("_", "-").lower()

    def field_name(self) -> str:
        return self.arg_name().removeprefix("--").replace("-", "_").lower()


class FallbackToEnv(ArgumentBuilder):
    def __init__(self, variable: str, fallback: MaybeString = _MISSING(), doc: MaybeString = _MISSING()):
        self.variable = variable
        self.fallback = fallback
        self._doc = doc
        self.value = _MISSING()  # type: MaybeString
        self._owner_name = None
        self._field_name = None

    @property
    def default(self) -> str | None:  # type: ignore[override]
        match self.fallback:
            case _MISSING():
                return get_environ(self.variable)
            case _:
                return get_environ(self.variable, self.fallback)

    def doc(self) -> str | None:
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
        arg_name = self._field_name or self.variable
        return "--" + arg_name.replace("_", "-").lower()

    def field_name(self) -> str:
        return self.arg_name().removeprefix("--").replace("-", "_").lower()
