import os
from argparse import ArgumentParser
from dataclasses import dataclass

from typing_extensions import Protocol


class _MISSING: ...


MaybeString = str | None | _MISSING


class CanAddArgument(Protocol):
    """This covers the private argparse._ArgumentGroup"""

    def add_argument(self, *args, **kwargs): ...


class FallbackToEnv:
    def __init__(self, variable: str, fallback: MaybeString = _MISSING(), doc: str | None = None):
        self.variable = variable
        self.fallback = fallback
        self._doc = doc
        self.value = _MISSING()  # type: MaybeString
        self._owner_name = None
        self._field_name = None

    def __set_name__(self, owner, name):
        """Capture the class and field name where this was defined"""
        self._owner_name = owner.__name__
        self._field_name = name

    def __set__(self, instance, value: str):
        self.value = value

    def __str__(self):
        return self.get()

    def get(self) -> str | None:
        match self.value:
            case _MISSING():
                return self.default
            case _:
                return self.value

    @property
    def default(self) -> str | None:
        match self.fallback:
            case _MISSING():
                return os.environ.get(self.variable)
            case _:
                return os.environ.get(self.variable, self.fallback)

    def doc(self):
        doc = self._doc
        if not doc.endswith("."):
            doc = f"{doc}."
        env = os.environ.get(self.variable, _MISSING())
        match env:
            case _MISSING():
                variable = f"${self.variable} (unset)"
            case _:
                variable = f"${self.variable}={env!r}"
        match self.fallback:
            case _MISSING():
                return f"{doc} Defaults to {variable}"

    def arg_name(self):
        arg_name = self._field_name or self.variable
        return "--" + arg_name.replace("_", "-").lower()

    def add_to_parser(self, parser: ArgumentParser | CanAddArgument):
        parser.add_argument(
            self.arg_name(),
            dest=self._field_name,
            default=self.default,
            help=self.doc(),
        )
