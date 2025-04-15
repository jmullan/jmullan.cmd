import abc
import os
from argparse import ArgumentParser

from typing_extensions import Protocol


class _MISSING: ...


MaybeString = str | None | _MISSING


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

    def add_to_parser(self, parser: ArgumentParser | CanAddArgument):
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
    def default(self) -> str | None:
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
    def default(self) -> str | None:
        match self.fallback:
            case _MISSING():
                return os.environ.get(self.variable)
            case _:
                return os.environ.get(self.variable, self.fallback)

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
        env = os.environ.get(self.variable, _MISSING())
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
