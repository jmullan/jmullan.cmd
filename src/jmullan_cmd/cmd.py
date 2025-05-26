"""Command-line tooling helpers."""

import abc
import argparse
import logging
import signal
import sys
from collections.abc import Callable
from typing import TextIO

logger = logging.getLogger(__name__)


class Jmullan:
    GO = True
    PIPE_OK = True


def handle_signal(signum, frame):
    if hasattr(signal, "SIGPIPE") and signal.SIGPIPE == signum:
        Jmullan.PIPE_OK = False
        sys.stderr.close()
        exit(128 + signum)

    if not Jmullan.GO:
        logger.debug("Received two signals, so immediately quitting")
        exit(128 + signum)
    Jmullan.GO = False


def handle_keyboard_interrupt():
    signal.signal(signal.SIGINT, handle_signal)


def broken_pipe_except_hook(exctype, value, traceback):
    if exctype is BrokenPipeError:
        Jmullan.PIPE_OK = False
        pass
    else:
        sys.__excepthook__(exctype, value, traceback)


def ignore_broken_pipe_error():
    if hasattr(signal, "SIGPIPE"):
        sys.excepthook = broken_pipe_except_hook
        # https://docs.python.org/3/library/signal.html#signal.signal
        # SIG_DFL: take default action (raise a broken pipe error)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def stop_on_broken_pipe_error():
    if hasattr(signal, "SIGPIPE"):
        sys.excepthook = broken_pipe_except_hook
        signal.signal(signal.SIGPIPE, handle_signal)


def open_via_requests(url: str) -> TextIO:
    from jmullan.cmd import requests_handle

    return requests_handle.RequestsHandle(url)  # type: ignore[return-value]


def open_file_or_stdin(filename: str) -> TextIO:
    if filename == "-":
        return sys.stdin
    elif filename.startswith("https://") or filename.startswith("http://"):
        return open_via_requests(filename)
    else:
        return open(filename)


def read_file_or_stdin(filename: str) -> str:
    with open_file_or_stdin(filename) as handle:
        return handle.read()


def write_to_file_or_stdout(filename: str, contents: str):
    if filename == "-":
        print(contents)
    else:
        with open(filename, "w") as f:
            f.write(contents)


def add_filenames_arguments(parser: argparse.ArgumentParser):
    parser.add_argument(
        "filenames",
        nargs="*",
        help=(
            "a list of files; - for stdin; separate arguments from"
            " files with an optional -- ; specifying no files means stdin"
        ),
    )


def get_filenames(args: argparse.Namespace):
    filenames = args.filenames or []
    if not filenames:
        filenames.append("-")
    return filenames


def update_in_place(filename: str, changer: Callable[[str], str]):
    contents = read_file_or_stdin(filename)
    new_contents = changer(contents)
    changed = new_contents != contents
    if changed:
        logger.debug(f"updated file {filename}\n")
        write_to_file_or_stdout(filename, new_contents)


def update_and_print(filename: str, changer: Callable[[str], str]):
    contents = read_file_or_stdin(filename)
    new_contents = changer(contents)
    changed = new_contents != contents
    if changed:
        print(new_contents)


def get_module_docstring(module_name: str) -> str | None:
    module = sys.modules.get(module_name)
    if module is not None:
        return module.__doc__
    return None


class Main(abc.ABC):
    def __init__(self):
        description = self.__doc__ or get_module_docstring(self.__module__)

        self.is_tty = sys.stdout.isatty()

        self.parser = argparse.ArgumentParser(
            formatter_class=self.get_argparse_formatter_class(), description=description, epilog=self.get_epilog()
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
        """Override me if you need a different formatter"""
        return argparse.RawDescriptionHelpFormatter

    def get_epilog(self) -> str:
        """Override me to add epilog items."""
        return ""

    def setup(self):
        stop_on_broken_pipe_error()
        handle_keyboard_interrupt()
        self.args = self.parser.parse_args()

    def main(self):
        self.setup()


class FileNameProcessor(Main, abc.ABC):
    @abc.abstractmethod
    def process_filename(self, filename: str):
        pass

    def get_filenames(self):
        """This allows overriding if needed"""
        return get_filenames(self.args)

    def setup(self):
        add_filenames_arguments(self.parser)
        super().setup()

    def main(self):
        super().main()
        for filename in self.get_filenames():
            if not Jmullan.GO:
                break
            self.process_filename(filename)


class ContentsProcessor(FileNameProcessor, abc.ABC):
    @abc.abstractmethod
    def process_contents(self, contents: str) -> str:
        pass


class InPlaceFileProcessor(ContentsProcessor, abc.ABC):
    def process_filename(self, filename: str):
        update_in_place(filename, self.process_contents)


class PrintingFileProcessor(ContentsProcessor, abc.ABC):
    def process_filename(self, filename: str):
        update_and_print(filename, self.process_contents)


class TextIoProcessor(FileNameProcessor, abc.ABC):
    @abc.abstractmethod
    def process_file_handle(self, filename: str, file_handle: TextIO):
        pass

    def process_filename(self, filename: str):
        with open_file_or_stdin(filename) as handle:
            self.process_file_handle(filename, handle)


class TextIoLineProcessor(TextIoProcessor, abc.ABC):
    @abc.abstractmethod
    def process_line(self, filename: str, line: str) -> tuple[bool, str]:
        pass

    def process_file_handle(self, filename: str, file_handle: TextIO):
        for line in file_handle:
            if not Jmullan.GO:
                break
            should_print, line = self.process_line(filename, line)
            if should_print:
                sys.stdout.write(line)
