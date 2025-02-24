"""Command-line tooling helpers."""

import abc
import logging
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from signal import SIG_DFL, SIGINT, signal, SIGPIPE
from typing import TextIO

import requests
from jmullan_logging.helpers import logging_context

logger = logging.getLogger(__name__)


class Jmullan:
    GO = True
    PIPE_OK = True


def my_except_hook(exctype, value, traceback):
    if exctype is BrokenPipeError:
        Jmullan.PIPE_OK = False
        pass
    else:
        sys.__excepthook__(exctype, value, traceback)


def handle_signal(signum, frame):
    logger.debug(f"Received signal {signum}")
    if SIGPIPE == signum:
        sys.stderr.close()
        exit(1)
    if not Jmullan.GO:
        logger.debug("Received two signals, so immediately quitting")
        exit(0)
    Jmullan.GO = False


def ignore_broken_pipe_error():
    sys.excepthook = my_except_hook
    signal(SIGPIPE, SIG_DFL)


def stop_on_broken_pipe_error():
    sys.excepthook = my_except_hook
    signal(SIGPIPE, handle_signal)


def handle_keyboard_interrupt():
    signal(SIGINT, handle_signal)


class RequestsHandle:
    def __init__(self, url: str):
        logger.debug("Opening url")
        self.url = url
        self.response = requests.get(url, stream=True)
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    """
    Text I/O implementation using an in-memory buffer.

    The initial_value argument sets the value of object.  The newline
    argument is like the one of TextIOWrapper's constructor.
    """

    def close(self, *args, **kwargs):  # real signature unknown
        """
        Close the IO object.

        Attempting any further operation after the object is closed
        will raise a ValueError.

        This method has no effect if the file is already closed.
        """
        self._closed = True
        try:
            if self.response is not None:
                self.response.close()
                self.response = None
        except Exception:
            with logging_context(external_http_url=self.url):
                logger.exception("Error closing request")

    def getvalue(self, *args, **kwargs) -> str:  # real signature unknown
        """Retrieve the entire contents of the object."""
        return self.response.text

    def read(self, size: int | None = None) -> str:  # real signature unknown
        """
        Read at most size characters, returned as a string.

        If the argument is negative or omitted, read until EOF
        is reached. Return an empty string at EOF.
        """
        try:
            if size is None:
                try:
                    return self.response.text
                finally:
                    self.close()
            else:
                # yield from self.response.iter_content(chunk_size=size, decode_unicode=True)
                return "".join(self.response.iter_content(chunk_size=size, decode_unicode=True))
        finally:
            self.close()

    def readable(self, *args, **kwargs):  # real signature unknown
        """Returns True if the IO object can be read."""
        return not self.closed

    def readline(self, size=-1, /):  # real signature unknown
        """
        Read until newline or EOF.

        Returns an empty string if EOF is hit immediately.
        """
        yield from self.response.iter_lines(chunk_size=size, decode_unicode=True)
        self.close()

    def seek(self, *args, **kwargs):  # real signature unknown
        """
        Change stream position.

        Seek to character offset pos relative to position indicated by whence:
            0  Start of stream (the default).  pos should be >= 0;
            1  Current position - pos must be 0;
            2  End of stream - pos must be 0.
        Returns the new absolute position.
        """
        raise NotImplementedError("Cannot seek from requests")

    def seekable(self, *args, **kwargs):  # real signature unknown
        """Returns True if the IO object can be seeked."""
        return False

    def tell(self, *args, **kwargs):  # real signature unknown
        """Tell the current file position."""
        if not self.closed:
            return self.response.raw.tell()

    def truncate(self, *args, **kwargs):  # real signature unknown
        """
        Truncate size to pos.

        The pos argument defaults to the current file position, as
        returned by tell().  The current file position is unchanged.
        Returns the new absolute position.
        """
        raise NotImplementedError("Cannot seek from requests")

    def writable(self, *args, **kwargs):  # real signature unknown
        """Returns True if the IO object can be written."""
        return False

    def write(self, *args, **kwargs):  # real signature unknown
        """
        Write string to file.

        Returns the number of characters written, which is always equal to
        the length of the string.
        """
        raise NotImplementedError("Cannot seek from requests")


def open_file_or_stdin(filename: str) -> TextIO:
    if filename == "-":
        return sys.stdin
    elif filename.startswith("https://") or filename.startswith("http://"):
        return RequestsHandle(filename)  # type: ignore[return-value]
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


def add_filenames_arguments(parser: ArgumentParser):
    parser.add_argument(
        "filenames",
        nargs="*",
        help=(
            "a list of files; - for stdin; separate arguments from"
            " files with an optional -- ; specifying no files means stdin"
        ),
    )


def get_filenames(args: Namespace):
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


def get_module_docstring(module_name: str):
    module = sys.modules.get(module_name)
    if module is not None:
        return module.__doc__


class Main(abc.ABC):
    def __init__(self):
        description = self.__doc__ or get_module_docstring(self.__module__)
        self.is_tty = sys.stdout.isatty()

        self.parser = ArgumentParser(description=description)
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
