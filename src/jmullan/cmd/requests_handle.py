"""Helpers that rely on requests live here."""

import logging
from collections.abc import Generator
from types import TracebackType
from typing import Literal

import requests

from jmullan.logging.helpers import logging_context  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


class RequestsHandle:
    """Provides a file-handle-like object for reading."""

    url: str
    response: requests.Response | None
    _closed: bool

    def __init__(self, url: str, timeout: int | None = None):
        """Get a url."""
        logger.debug("Opening url")
        self.url = url
        self.response = requests.get(url, stream=True, timeout=timeout)
        self._closed = False

    def __enter__(self) -> "RequestsHandle":
        """Provide this object as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        """Clean up when using this object as a context manager."""
        self.close()
        return False

    def close(self, *args, **kwargs) -> None:  # real signature unknown
        """Close the IO object.

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

    def getvalue(self, *args, **kwargs) -> str | None:  # real signature unknown
        """Retrieve the entire contents of the object."""
        if self.response is None:
            return None
        return self.response.text

    def read(self, size: int | None = None) -> str | None:  # real signature unknown
        """Read at most size characters, returned as a string.

        If the argument is negative or omitted, read until EOF
        is reached. Return an empty string at EOF.
        """
        if self.response is None:
            return None
        try:
            if size is None:
                return self.response.text
            return "".join(self.response.iter_content(chunk_size=size, decode_unicode=True))
        finally:
            self.close()

    def readable(self, *args, **kwargs) -> bool:  # real signature unknown
        """Return True if the IO object can be read."""
        return self.response is not None and not self._closed

    def readline(self, size: int | None = -1, /) -> Generator[str, None, None]:  # real signature unknown
        """Read until newline or EOF.

        Returns an empty string if EOF is hit immediately.
        """
        if self.response is None:
            return
        yield from self.response.iter_lines(chunk_size=size, decode_unicode=True)
        self.close()

    def seek(self, *args, **kwargs) -> None:  # real signature unknown
        """Change stream position.

        Seek to character offset pos relative to position indicated by whence:
            0  Start of stream (the default).  pos should be >= 0;
            1  Current position - pos must be 0;
            2  End of stream - pos must be 0.
        Returns the new absolute position.
        """
        raise NotImplementedError("Cannot seek from requests")

    @staticmethod
    def seekable(*args, **kwargs) -> bool:  # real signature unknown
        """Return True if the IO object can be seeked."""
        return False

    def tell(self, *args, **kwargs) -> int | None:  # real signature unknown
        """Tell the current file position."""
        if self.response is None:
            return None
        if self.readable():
            return self.response.raw.tell()
        return None

    def truncate(self, *args, **kwargs) -> None:  # real signature unknown
        """Truncate size to pos.

        The pos argument defaults to the current file position, as
        returned by tell().  The current file position is unchanged.
        Returns the new absolute position.
        """
        raise NotImplementedError("Cannot seek from requests")

    def writable(self, *args, **kwargs) -> bool:  # real signature unknown
        """Return True if the IO object can be written."""
        return False

    def write(self, *args, **kwargs) -> None:  # real signature unknown
        """Write string to file.

        Returns the number of characters written, which is always equal to
        the length of the string.
        """
        raise NotImplementedError("Cannot seek from requests")
