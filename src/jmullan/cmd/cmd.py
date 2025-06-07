"""# Command-line tooling helpers."""

import abc
import argparse
import logging
import pathlib
import signal
import sys
from collections.abc import Callable
from types import FrameType, TracebackType
from typing import TextIO

import jmullan.cmd.auto_config

logger = logging.getLogger(__name__)


class Jmullan:
    """Hold some globals as class members."""

    GO = True
    PIPE_OK = True


def handle_signal(signum: int, _: FrameType | None) -> None:
    """Handle signals like SIGINT or SIGPIPE."""
    if hasattr(signal, "SIGPIPE") and signum == signal.SIGPIPE:
        Jmullan.PIPE_OK = False
        sys.stderr.close()
        sys.exit(128 + signum)

    if not Jmullan.GO:
        logger.debug("Received two signals, so immediately quitting")
        sys.exit(128 + signum)
    Jmullan.GO = False


def handle_keyboard_interrupt() -> None:
    """Turn a keyboard interrupt into a signal."""
    signal.signal(signal.SIGINT, handle_signal)


def broken_pipe_except_hook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """Note or re-raise a broken pipe."""
    if exc_type is BrokenPipeError:
        Jmullan.PIPE_OK = False
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def ignore_broken_pipe_error() -> bool:
    """Ignore broken pipes rather than crashing noisily.

    Does not work in Windows because there is no SIGPIPE.
    """
    if hasattr(signal, "SIGPIPE"):
        sys.excepthook = broken_pipe_except_hook
        # https://docs.python.org/3/library/signal.html#signal.signal
        # SIG_DFL: take default action (raise a broken pipe error)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        return True
    return False


def stop_on_broken_pipe_error() -> bool:
    """Stop everything if the pipe is broken.

    Does not work in Windows because there is no SIGPIPE.
    """
    if hasattr(signal, "SIGPIPE"):
        sys.excepthook = broken_pipe_except_hook
        signal.signal(signal.SIGPIPE, handle_signal)
        return True
    return False


def open_via_requests(url: str) -> TextIO:
    """Open a url as though it were a file."""
    from jmullan.cmd import requests_handle

    return requests_handle.RequestsHandle(url)  # type: ignore[return-value]


def open_file_or_stdin(filename: str) -> TextIO:
    """Open a file, use stdin, or make an http request."""
    if filename == "-":
        return sys.stdin
    if filename.startswith(("https://", "http://")):
        return open_via_requests(filename)
    return pathlib.Path(filename).open("r", encoding="utf-8", newline="\n")


def read_file_or_stdin(filename: str) -> str:
    """Open and read a file, stdin, or a url."""
    with open_file_or_stdin(filename) as handle:
        return handle.read()


def write_to_file_or_stdout(filename: str, contents: str) -> None:
    """Open and write to a file or stdout."""
    if filename == "-":
        sys.stdout.write(contents)
        sys.stdout.flush()
    else:
        with pathlib.Path(filename).open("w", encoding="utf-8", newline="\n") as f:
            f.write(contents)


def add_filenames_arguments(parser: argparse.ArgumentParser) -> None:
    """Add filename arguments to a parser."""
    parser.add_argument(
        "filenames",
        nargs="*",
        help=(
            "A list of files; - for stdin; separate arguments from"
            " files with an optional -- ; specifying no files means stdin"
        ),
    )


def get_filenames(args: argparse.Namespace) -> list[str]:
    """Extract filenames from args.

    If no filenames are provided, returns "-", which is used as a placeholder
    for stdin.
    """
    filenames = args.filenames or []
    if not filenames:
        filenames.append("-")
    return filenames


def update_in_place(filename: str, changer: Callable[[str], str]) -> None:
    """Load a file, transform its contents, and write them back into the file."""
    contents = read_file_or_stdin(filename)
    new_contents = changer(contents)
    changed = new_contents != contents
    if changed:
        logger.debug("updated file %s", filename)
        write_to_file_or_stdout(filename, new_contents)


def update_and_print(filename: str, changer: Callable[[str], str]) -> None:
    """Load a file, transform its contents, and print them out."""
    contents = read_file_or_stdin(filename)
    new_contents = changer(contents)
    changed = new_contents != contents
    if changed:
        sys.stdout.write(new_contents)
        sys.stdout.flush()


def get_module_docstring(module_name: str) -> str | None:
    """Try to load a module and extract its docstring."""
    module = sys.modules.get(module_name)
    if module is not None:
        return module.__doc__
    return None


def find_method_help(method: Callable | None) -> str | None:
    """Check a method's docstring to see if it can be used for a help message."""
    if method is None:
        return None
    if getattr(method, "__isabstractmethod__", False):
        return None
    return method.__doc__


def find_command_help(command: object) -> str | None:
    """Examine strings to find the first candidate to use as help."""
    if command is None:
        return None
    clazz = getattr(command, "__class__", object)
    if bool(getattr(clazz, "__abstractmethods__", None)):
        return None

    docs = [
        find_method_help(getattr(command, "main", object)),
        find_method_help(getattr(command, "__init__", object)),
        command.__doc__,
        get_module_docstring(command.__module__),
    ]
    for doc in docs:
        if doc is not None and len(doc.strip()) and not doc.startswith("#"):
            return doc
    return None


class Main(abc.ABC):
    """#A base class for your command.

    Extend this or one of the child classes and override the appropriate parts.

    jmullan.cmd will attempt to use docstrings to form argparse command help.

    jmullan.cmd will ignore docstrings in abstract classes and docstrings
    prefixed with #.
    """

    def __init__(self):
        """#Construct the command."""
        description = find_command_help(self)

        self.is_tty = sys.stdout.isatty()

        self.parser = argparse.ArgumentParser(
            formatter_class=self.get_argparse_formatter_class(),
            description=description,
            epilog=self.get_epilog(),
        )
        self.parser.add_argument(
            "-v",
            "--verbose",
            dest="verbose",
            action="store_true",
            default=False,
            help="verbose is more verbose",
        )
        self.parser.add_argument(
            "-q",
            "--quiet",
            dest="quiet",
            action="store_true",
            default=False,
            help="do not log anything",
        )
        self.args = None

    def get_argparse_formatter_class(self) -> type[argparse.HelpFormatter]:
        """Override me if you need a different formatter."""
        return jmullan.cmd.auto_config.AHelpFormatter

    def get_epilog(self) -> str:
        """Override me to add epilog items."""
        return ""

    def setup(self) -> None:
        """Handle exceptions and parse arguments.

        Override setup() with any extra setup.
        """
        stop_on_broken_pipe_error()
        handle_keyboard_interrupt()
        self.args = self.parser.parse_args()

    @abc.abstractmethod
    def main(self) -> None:
        """#Override this method for the body of your command.

        This is marked as abstract, but you should call it, or at least call
        setup() in your class.
        """
        self.setup()


class FileNameProcessor(Main, abc.ABC):
    """A base class for processing filenames."""

    @abc.abstractmethod
    def process_filename(self, filename: str) -> None:
        """Do something with the given filename.

        This is for you to implement.
        """

    def get_filenames(self) -> list[str]:
        """Get a list of filenames from the command line arguments.

        This allows overriding if needed
        """
        return get_filenames(self.args)

    def setup(self) -> None:
        """Add filename arguments to the parser."""
        add_filenames_arguments(self.parser)
        super().setup()

    def main(self) -> None:
        """Process all the requested filenames."""
        super().main()
        for filename in self.get_filenames():
            if not Jmullan.GO:
                break
            self.process_filename(filename)


class ContentsProcessor(FileNameProcessor, abc.ABC):
    """Processes the full text contents of a file."""

    @abc.abstractmethod
    def process_contents(self, contents: str) -> str:
        """Process the full text contents of a file.

        This is for you to implement.
        """


class InPlaceFileProcessor(ContentsProcessor, abc.ABC):
    """Process a file and write it back out in place."""

    def process_filename(self, filename: str) -> None:
        """Process a filename and write it back out in place."""
        update_in_place(filename, self.process_contents)


class PrintingFileProcessor(ContentsProcessor, abc.ABC):
    """Process a file and print the output."""

    def process_filename(self, filename: str) -> None:
        """Process a filename and print the result."""
        update_and_print(filename, self.process_contents)


class TextIoProcessor(FileNameProcessor, abc.ABC):
    """A file processor for reading and processing the entire contents at once.."""

    @abc.abstractmethod
    def process_file_handle(self, filename: str, file_handle: TextIO) -> None:
        """Process a file handle.

        This is for you to implement.
        """

    def process_filename(self, filename: str) -> None:
        """Open and process a filename."""
        with open_file_or_stdin(filename) as handle:
            self.process_file_handle(filename, handle)


class TextIoLineProcessor(TextIoProcessor, abc.ABC):
    """A file processor for processing one line at a time."""

    @abc.abstractmethod
    def process_line(self, filename: str, line: str) -> tuple[bool, str]:
        """Process one line of a file handle.

        This is for you to implement.
        """

    def process_file_handle(self, filename: str, file_handle: TextIO) -> None:
        """Process a file handle line by line."""
        for line in file_handle:
            if not Jmullan.GO:
                break
            should_print, processed = self.process_line(filename, line)
            if should_print:
                sys.stdout.write(processed)
